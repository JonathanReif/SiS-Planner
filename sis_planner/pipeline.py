"""End-to-end pipeline: SiS descriptions + request -> ranked simulation sequences."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from importlib import resources
from typing import List

from rdflib import Graph

from .evaluation import DEFAULT_PARAMETERS, QualityKnowledge, ScoringParameters, evaluate_and_rank, plan_nodes
from .planner_bridge import run_planner
from .translate import Request, SimulationDescription, build_view


def schema_graph() -> Graph:
    g = Graph()
    g.parse(data=resources.files("sis_planner.schema").joinpath("planner_schema.ttl").read_text(encoding="utf-8"),
            format="turtle")
    return g


@dataclass
class PlanningOutcome:
    request: Request
    simulations: List[SimulationDescription]
    result_type: str
    raw_plans: List[dict]
    ranked: List[dict]
    view: Graph
    seconds: float
    parameters: ScoringParameters = DEFAULT_PARAMETERS

    def sequences(self) -> List[List[str]]:
        return [[n.clean_iri for n in plan_nodes(e["plan"])] for e in self.ranked]

    def to_json(self) -> dict:
        req = self.request
        return {
            "request": {
                "requiredCapability": str(req.capability),
                "process": str(req.process) if req.process else None,
                "knownInputs": [str(t) for t in req.known_inputs],
                "wantedOutputs": [str(t) for t in req.wanted_outputs],
                "requiredQuality": [{"typeDescription": q.type_description, "value": q.value,
                                     "logicInterpretation": q.logic_interpretation, "weight": q.weight}
                                    for q in req.required_quality],
            },
            "scoringParameters": asdict(self.parameters),
            "consideredSimulations": [str(s.simulation) for s in self.simulations],
            "resultType": self.result_type,
            "numberOfPlans": len(self.raw_plans),
            "seconds": round(self.seconds, 2),
            "sequences": [{
                "rank": e["rank"],
                "capabilities": [n.clean_iri for n in plan_nodes(e["plan"])],
                "meetsRequirements": e["evaluation"]["meetsRequirements"],
                "overallScore": e["evaluation"]["overallScore"],
                "efficiencyTieBreaker": e["evaluation"]["efficiencyTieBreaker"],
                "criteria": e["evaluation"]["criteria"],
                "plan": e["plan"],
            } for e in self.ranked],
        }


def plan(knowledge: Graph, request_graph: Graph, max_happenings: int = 20, use_process_filter: bool = True,
         verbose: bool = False, parameters: ScoringParameters = DEFAULT_PARAMETERS) -> PlanningOutcome:
    t0 = time.time()
    view, req, sims, info = build_view(knowledge, request_graph, use_process_filter)
    working = view + schema_graph()
    result = run_planner(working, str(req.capability), None, max_happenings, True, verbose).to_json()
    plans = result.get("plans") or ([result["plan"]] if result.get("plan") else [])
    plans = [p for p in plans if p.get("plan_steps")]
    knowledge_q = QualityKnowledge(working, info.auxiliary, info.variable_types)
    ranked = evaluate_and_rank(plans, req.required_quality, knowledge_q, parameters) if plans else []
    return PlanningOutcome(req, sims, result.get("resultType", "unknown"), plans, ranked, working,
                           time.time() - t0, parameters)
