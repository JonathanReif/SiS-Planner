"""Loading of SiS descriptions from files or from a SPARQL endpoint (read-only)."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import requests
from rdflib import Graph
from rdflib.namespace import OWL

RDF_SUFFIXES = {".ttl": "turtle", ".owl": "xml", ".rdf": "xml", ".nt": "nt", ".n3": "n3", ".jsonld": "json-ld", ".trig": "trig"}

CONSTRUCT_ALL = """
CONSTRUCT { ?s ?p ?o } WHERE {
  { ?s ?p ?o } UNION { GRAPH ?g { ?s ?p ?o } }
}"""


def load_files(paths: Iterable[str | Path]) -> Graph:
    """Load RDF files; directories are searched recursively. owl:imports are not followed."""
    g = Graph()
    for p in paths:
        p = Path(p)
        files = sorted(f for f in p.rglob("*") if f.suffix.lower() in RDF_SUFFIXES) if p.is_dir() else [p]
        if p.is_dir() and not files:
            raise FileNotFoundError(f"No RDF files found in {p}")
        for f in files:
            fmt = RDF_SUFFIXES.get(f.suffix.lower())
            if f.suffix.lower() == ".trig":
                from rdflib import Dataset
                ds = Dataset()
                ds.parse(f, format="trig")
                for s, pr, o, _ in ds.quads():
                    g.add((s, pr, o))
            else:
                g.parse(f, format=fmt)
    g.remove((None, OWL.imports, None))
    return g


def load_endpoint(endpoint_url: str, timeout: int = 300, user: str | None = None, password: str | None = None) -> Graph:
    """Read all explicit statements (default graph and named graphs) of a SPARQL endpoint.

    For GraphDB the repository URL is the endpoint, e.g. http://localhost:7200/repositories/<repo>.
    Inferred statements are not requested (``infer=false``), the planning works on explicit data.
    """
    response = requests.post(endpoint_url, data={"query": CONSTRUCT_ALL, "infer": "false"},
                             headers={"Accept": "application/n-triples"}, timeout=timeout,
                             auth=(user, password) if user else None)
    response.raise_for_status()
    g = Graph()
    g.parse(data=response.content.decode("utf-8"), format="nt")
    g.remove((None, OWL.imports, None))
    return g
