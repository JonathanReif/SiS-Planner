"""Bridge between an in-memory working graph and the vendored CaSkade planning core.

The planning core (package ``smt_planning``) is used unchanged. It normally loads its
knowledge either from a file (following ``owl:imports``) or from a SPARQL endpoint.
The SiS-Planner instead hands over a prepared working graph that already contains the
planning view derived from the SiS descriptions.

The working graph is loaded into an embedded Oxigraph store. Query results are handed to
the planning core in the same form as the core's SPARQL endpoint handler produces them
(IRIs as ``URIRef``, every other term as a plain ``Literal`` of its lexical value), so that
the planning core behaves exactly as it does against a GraphDB endpoint.
"""
from __future__ import annotations

import contextlib
import io
import re
from typing import Optional

import pyoxigraph as ox
from rdflib import Graph, Literal, URIRef, Variable
from rdflib.query import Result

from smt_planning.ontology_handling.query_handlers import QueryHandler
from smt_planning.smt.StateHandler import StateHandler
from smt_planning.smt.cask_to_smt import CaskadePlanner
from smt_planning.planning_result import PlanningResult


def to_store(graph: Graph) -> ox.Store:
    """Copy an rdflib graph into an in-memory Oxigraph store."""
    store = ox.Store()
    store.load(graph.serialize(format="nt", encoding="utf-8"), format=ox.RdfFormat.N_TRIPLES)
    return store


# Some queries of the planning core use prefixes without declaring them (GraphDB and rdflib
# resolve them implicitly). Missing declarations are added from this list.
DEFAULT_PREFIXES = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "CSS": "http://www.w3id.org/hsu-aut/css#",
    "CaSk": "http://www.w3id.org/hsu-aut/cask#",
    "DINEN61360": "http://www.w3id.org/hsu-aut/DINEN61360#",
    "VDI3682": "http://www.w3id.org/hsu-aut/VDI3682#",
    "VDI3633": "http://www.semanticweb.org/reif/ontologies/VDI3633#",
    "SiS": "http://www.semanticweb.org/reif/ontologies/SiS#",
    "OM": "http://openmath.org/vocab/math#",
}


def compatible(query_string: str) -> str:
    """Adapt a query of the planning core to strict SPARQL 1.1 as implemented by Oxigraph.

    GraphDB and rdflib accept IRIs in GROUP_CONCAT and resolve undeclared standard prefixes.
    Oxigraph does neither, so IRIs are converted with STR() and missing prefixes are declared.
    """
    query_string = re.sub(r"GROUP_CONCAT\(\s*(DISTINCT\s+)?(\?\w+)", r"GROUP_CONCAT(\1STR(\2)",
                          query_string, flags=re.IGNORECASE)
    return with_prefixes(query_string)


def with_prefixes(query_string: str) -> str:
    declared = set(re.findall(r"PREFIX\s+([A-Za-z][\w-]*)\s*:", query_string, flags=re.IGNORECASE))
    body = re.sub(r"<[^<>\s]*>", "<>", query_string)  # ignore full IRIs
    missing = [f"PREFIX {p}: <{iri}>" for p, iri in DEFAULT_PREFIXES.items()
               if p not in declared and re.search(rf"(?<![\w-]){re.escape(p)}:", body)]
    return "\n".join(missing + [query_string]) if missing else query_string


class OxigraphQueryHandler(QueryHandler):
    """Answers the planning core's SPARQL queries on an embedded Oxigraph store."""

    def __init__(self, store: ox.Store) -> None:
        self.store = store

    def query(self, query_string: str) -> Result:
        solutions = self.store.query(compatible(query_string))
        labels = [Variable(v.value) for v in solutions.variables]
        rows = []
        for solution in solutions:
            row = {}
            for label in labels:
                term = solution[str(label)]
                if term is None:
                    continue
                row[label] = URIRef(term.value) if isinstance(term, ox.NamedNode) else Literal(term.value)
            rows.append(row)
        result = Result("SELECT")
        result.vars = labels
        result.bindings = rows
        return result


def run_planner(graph: Graph,
                required_capability_iri: str,
                process_iri: Optional[str] = None,
                max_happenings: int = 20,
                find_all_solutions: bool = True,
                verbose: bool = False) -> PlanningResult:
    """Run the CaSkade planning core on ``graph`` and return its planning result."""
    # The planning core prints extensive diagnostic output, which is hidden unless requested.
    quiet = contextlib.nullcontext() if verbose else _silenced()
    with quiet:
        planner = CaskadePlanner(required_capability_iri, process_iri)
        planner.query_handler = OxigraphQueryHandler(to_store(graph))
        StateHandler().set_graph(graph)
        return planner.cask_to_smt(max_happenings, None, None, None, find_all_solutions)


@contextlib.contextmanager
def _silenced():
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        yield
