"""Multi-criteria evaluation of candidate simulation sequences.

For every required quality criterion the quality is propagated along the capability chain
of a plan:

* Every capability has an intrinsic quality value for the criterion (``SiS:QualityCriteria``
  of the simulation that provides the capability). A missing value counts as 1.0.
* For every input of a capability the deficit ``intrinsic - input quality`` (if positive) is
  weighted with the influence of that input on the criterion (``SiS:hasInfluence`` /
  ``SiS:hasInfluenceOn``, value of ``SiS:InfluenceScore`` or ``SiS:SensitivityIndex``,
  default 1.0). The largest weighted deficit is subtracted from the intrinsic quality.
* The output quality is passed on to the data produced by the capability. Data is identified
  by the type description of its data element, as in the planning.
* The value of the sequence is the minimum over all terminal outputs.

The score of a criterion is f(output, target) with alpha_under = 0.1, s_max = 1.5 and
delta = 1.0. The sequence score is the product of the criterion scores raised to their weights
(default 1.0). Without any time-related requirement an implicit efficiency tie-breaker based
on SimTime and TRL is applied.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from rdflib import Graph, URIRef

from .vocab import DINEN61360, MATH, NS_PREFIXES

@dataclass(frozen=True)
class ScoringParameters:
    """Parameters of the score function. They are use-case specific and should be chosen
    together with domain experts; the defaults are the values used in the original evaluation."""
    alpha_under: float = 0.1         # score of a criterion that misses its target
    s_max: float = 1.5               # asymptotic upper bound of the bonus for over-fulfilment
    delta: float = 1.0               # growth factor of the bonus
    tie_breaker_weight: float = 0.5  # exponent of the implicit efficiency tie-breaker


DEFAULT_PARAMETERS = ScoringParameters()


def local_name(iri: str) -> str:
    idx = iri.rfind("#")
    return iri[idx + 1:] if idx >= 0 else iri.rstrip("/").split("/")[-1]


def criterion_type(type_description: str) -> str:
    """Criterion type: local name of the type description without the suffix _TD."""
    name = local_name(type_description)
    return name[:-3] if name.endswith("_TD") else name


@dataclass
class RequiredQuality:
    type_description: str
    value: float
    logic_interpretation: str = ">="
    weight: float = 1.0

    @property
    def criterion_type(self) -> str:
        return criterion_type(self.type_description)


@dataclass
class PlanNode:
    capability_iri: str
    step_index: int
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)

    @property
    def clean_iri(self) -> str:
        return re.sub(r"_\d+_\d+$", "", self.capability_iri)


def plan_nodes(plan_json: dict) -> List[PlanNode]:
    """Capability nodes of a plan in step order."""
    nodes = []
    for step in plan_json.get("plan_steps", []):
        for app in step.get("capability_applications", []):
            nodes.append(PlanNode(app["capability_iri"], step["step_number"],
                                  [i["property_iri"] for i in app.get("inputs") or []],
                                  [o["property_iri"] for o in app.get("outputs") or []]))
    return nodes


def plan_signature(plan_json: dict) -> str:
    """Sorted capability IRIs. Plans with the same signature are the same sequence."""
    return "|".join(sorted(n.capability_iri for n in plan_nodes(plan_json)))


class QualityKnowledge:
    """Quality values and influences read from the planning view of the working graph."""

    def __init__(self, graph: Graph, ignored_inputs: Optional[set] = None,
                 variable_types: Optional[Dict[str, str]] = None) -> None:
        self.graph = graph
        # OpenMath variables of interdependencies -> type description of the referenced datum
        self.variable_types = dict(variable_types or {})
        # interdependencies[(capability, criterion type)][input data element] = root of the expression
        self.interdependencies: Dict[tuple, Dict[str, URIRef]] = {}
        # intrinsic[(capability, criterion type)] = value
        self.intrinsic_values: Dict[tuple, float] = {}
        # influences[(capability, criterion type)][input data element] = value
        self.influences: Dict[tuple, Dict[str, float]] = {}
        # type description of every data element (identifies the data in the data flow)
        self.type_of: Dict[str, str] = {}
        # auxiliary inputs of the planning encoding, not part of the data flow
        self.ignored_inputs = {str(i) for i in (ignored_inputs or set())}
        for de, td in graph.subject_objects(URIRef(str(DINEN61360) + "has_Type_Description")):
            self.type_of[str(de)] = str(td)
        q_intrinsic = NS_PREFIXES + """
        SELECT ?cap ?td ?value WHERE {
            ?res CSS:providesCapability ?cap ;
                 SiS:hasQualityCriteria ?qc .
            ?qc DINEN61360:has_Data_Element ?de .
            ?de DINEN61360:has_Type_Description ?td ;
                DINEN61360:has_Instance_Description ?id .
            ?id DINEN61360:Value ?value ;
                DINEN61360:Expression_Goal "Assurance" .
        }"""
        for row in graph.query(q_intrinsic):
            self.intrinsic_values[(str(row.cap), criterion_type(str(row.td)))] = float(row.value)
        q_influence = NS_PREFIXES + """
        SELECT ?cap ?td ?inputDe ?value WHERE {
            ?process CSS:requiresCapability ?cap .
            ?influence SiS:isInfluenceFor ?process ;
                       SiS:hasInfluenceOn ?qc ;
                       DINEN61360:has_Data_Element ?de .
            ?de DINEN61360:has_Instance_Description/DINEN61360:Value ?value .
            FILTER NOT EXISTS { ?de a SiS:Interdependency }
            ?input SiS:hasInfluence ?influence ;
                   DINEN61360:has_Data_Element ?inputDe .
            ?qc DINEN61360:has_Data_Element/DINEN61360:has_Type_Description ?td .
        } ORDER BY ?cap ?td ?inputDe ?influence"""
        for row in graph.query(q_influence):
            key = (str(row.cap), criterion_type(str(row.td)))
            self.influences.setdefault(key, {})[str(row.inputDe)] = float(row.value)
        q_interdependency = NS_PREFIXES + """
        SELECT ?cap ?td ?inputDe ?root WHERE {
            ?process CSS:requiresCapability ?cap .
            ?influence SiS:isInfluenceFor ?process ;
                       SiS:hasInfluenceOn ?qc ;
                       DINEN61360:has_Data_Element ?de .
            ?de a SiS:Interdependency ;
                CSS:isRestrictedBy ?root .
            ?input SiS:hasInfluence ?influence ;
                   DINEN61360:has_Data_Element ?inputDe .
            ?qc DINEN61360:has_Data_Element/DINEN61360:has_Type_Description ?td .
        }"""
        for row in graph.query(q_interdependency):
            key = (str(row.cap), criterion_type(str(row.td)))
            self.interdependencies.setdefault(key, {})[str(row.inputDe)] = row.root

    def intrinsic(self, cap: str, ctype: str) -> float:
        return self.intrinsic_values.get((cap, ctype), 1.0)

    def influence(self, cap: str, ctype: str, input_de: str, state: Optional[Dict[str, float]] = None) -> float:
        """Influence of an input on a criterion. Interdependencies are evaluated with the current
        quality state, scalar influences are taken as given, otherwise 1.0."""
        root = self.interdependencies.get((cap, ctype), {}).get(input_de)
        if root is not None:
            value = evaluate_openmath(self.graph, root, state or {}, self.variable_types)
            if value is not None:
                return value
        return self.influences.get((cap, ctype), {}).get(input_de, 1.0)

    def datum(self, data_element: str) -> str:
        """Identity of a datum in the data flow: its type description."""
        return self.type_of.get(data_element, data_element)


OPENMATH_OPERATORS = {
    "http://www.openmath.org/cd/arith1#plus": lambda a: sum(a),
    "http://www.openmath.org/cd/arith1#minus": lambda a: a[0] - a[1] if len(a) == 2 else (-a[0] if len(a) == 1 else None),
    "http://www.openmath.org/cd/arith1#times": lambda a: math.prod(a),
    "http://www.openmath.org/cd/arith1#divide": lambda a: a[0] / a[1] if len(a) == 2 and a[1] != 0 else None,
    "http://www.openmath.org/cd/arith1#power": lambda a: a[0] ** a[1] if len(a) == 2 else None,
    "http://www.openmath.org/cd/arith1#root": lambda a: a[0] ** 0.5 if len(a) == 1 else (a[0] ** (1 / a[1]) if len(a) == 2 and a[1] else None),
    "http://www.openmath.org/cd/arith1#abs": lambda a: abs(a[0]) if len(a) == 1 else None,
    "http://www.openmath.org/cd/minmax1#min": lambda a: min(a) if a else None,
    "http://www.openmath.org/cd/minmax1#max": lambda a: max(a) if a else None,
}


def evaluate_openmath(graph: Graph, node, state: Dict[str, float], variable_types: Dict[str, str],
                      depth: int = 0) -> Optional[float]:
    """Evaluate an OpenMath application to a number.

    Literals (math:value) are taken as given. Variables are instance descriptions of data; they
    are replaced by the propagated quality of that datum, or 1.0 if the datum has not been
    produced by a preceding simulation. Returns None if the expression cannot be evaluated.
    """
    if depth > 20:
        return None
    operator = graph.value(node, URIRef(str(MATH) + "operator"))
    op = OPENMATH_OPERATORS.get(str(operator))
    if op is None:
        return None
    values = []
    for arg in graph.items(graph.value(node, URIRef(str(MATH) + "arguments"))):
        if graph.value(arg, URIRef(str(MATH) + "operator")) is not None:
            v = evaluate_openmath(graph, arg, state, variable_types, depth + 1)
            if v is None:
                return None
        elif graph.value(arg, URIRef(str(MATH) + "value")) is not None:
            v = float(graph.value(arg, URIRef(str(MATH) + "value")))
        else:
            v = state.get(variable_types.get(str(arg), ""), 1.0)
        values.append(v)
    try:
        return op(values)
    except (ArithmeticError, ValueError):
        return None


def criterion_score(produced: float, required: RequiredQuality,
                    params: ScoringParameters = DEFAULT_PARAMETERS) -> tuple[bool, float]:
    """Asymmetric score function f(output, target)."""
    target = required.value
    logic = required.logic_interpretation or ">="
    if logic == "<=":
        meets = produced <= target
        rel = (target - produced) / target if target else 0.0
    elif logic == "=":
        meets = abs(produced - target) < 0.001
        rel = abs(produced - target) / target if target else 0.0
    else:
        meets = produced >= target
        rel = (produced - target) / target if target else 0.0
    if not meets:
        return False, params.alpha_under
    return True, 1.0 + (params.s_max - 1.0) * (1.0 - math.exp(-params.delta * rel))


def evaluate_plan(nodes: List[PlanNode], required: List[RequiredQuality], knowledge: QualityKnowledge,
                  params: ScoringParameters = DEFAULT_PARAMETERS) -> dict:
    overall, meets_all, evaluations = 1.0, True, []
    for req in required:
        ctype = req.criterion_type
        state: Dict[str, float] = {}
        consumed, produced = set(), []
        chain = []
        for node in nodes:
            cap = node.clean_iri
            q_int = knowledge.intrinsic(cap, ctype)
            worst, dominant, worst_input = 0.0, 1.0, 1.0
            for inp in node.inputs:
                if inp in knowledge.ignored_inputs:
                    continue
                key = knowledge.datum(inp)
                consumed.add(key)
                q_in = state.get(key, 1.0)
                factor = knowledge.influence(cap, ctype, inp, state)
                if q_in < q_int:
                    weighted = (q_int - q_in) * factor
                    if weighted > worst:
                        worst, dominant, worst_input = weighted, factor, q_in
            q_out = max(0.0, q_int - worst)
            for out in (node.outputs or [cap]):
                key = knowledge.datum(out)
                state[key] = q_out
                if key not in produced:
                    produced.append(key)
            chain.append({"capability": cap, "inputQuality": worst_input, "intrinsicQuality": q_int,
                          "influence": dominant, "outputQuality": q_out})
        terminal = [o for o in produced if o not in consumed] or produced
        value = min(state.get(o, 1.0) for o in terminal) if terminal else 1.0
        ok, score = criterion_score(value, req, params)
        meets_all = meets_all and ok
        overall *= score ** req.weight
        evaluations.append({"criterion": ctype, "typeDescription": req.type_description,
                            "logicInterpretation": req.logic_interpretation or ">=",
                            "requiredValue": req.value, "producedValue": value, "meets": ok,
                            "score": score, "weight": req.weight, "propagation": chain})
    # Implicit efficiency tie-breaker (only without time-related requirements)
    has_time = any(s in r.type_description for r in required for s in ("SimTime", "Time", "Speed"))
    tie_breaker = None
    if not has_time and meets_all:
        eff = 1.0
        for node in nodes:
            trl = knowledge.intrinsic(node.clean_iri, "TRL")
            trl = min(1.0, trl / 9.0) if trl > 1.0 else trl
            eff *= knowledge.intrinsic(node.clean_iri, "SimTime") * trl
        tie_breaker = eff ** params.tie_breaker_weight
        overall *= tie_breaker
    return {"meetsRequirements": meets_all, "overallScore": overall,
            "efficiencyTieBreaker": tie_breaker, "criteria": evaluations}


def evaluate_and_rank(plans: List[dict], required: List[RequiredQuality], knowledge: QualityKnowledge,
                      params: ScoringParameters = DEFAULT_PARAMETERS) -> List[dict]:
    """Evaluate all plans, merge plans with the same capabilities and rank them.

    Ranking: sequences meeting all requirements first, then by descending overall score.
    Duplicates (same set of capabilities in a different step order) are merged after sorting,
    keeping the first occurrence.
    """
    evaluated = [{"plan": p, "evaluation": evaluate_plan(plan_nodes(p), required, knowledge, params)} for p in plans]
    evaluated.sort(key=lambda e: (not e["evaluation"]["meetsRequirements"], -e["evaluation"]["overallScore"]))
    unique, seen = [], set()
    for e in evaluated:
        sig = plan_signature(e["plan"])
        if sig not in seen:
            seen.add(sig)
            unique.append(e)
    for rank, e in enumerate(unique, 1):
        e["rank"] = rank
    return unique
