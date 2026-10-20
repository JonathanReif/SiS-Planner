"""Plain-text report of a planning outcome."""
from __future__ import annotations

from typing import List

from .evaluation import local_name, plan_nodes
from .pipeline import PlanningOutcome


def short(iri: str) -> str:
    name = local_name(iri)
    for suffix in ("Capability", "_TD"):
        if name.endswith(suffix):
            return name[:-len(suffix)]
    return name


def pct(x: float) -> str:
    return f"{x * 100:.1f} %"


def num(x: float) -> str:
    return f"{x:.3f}"


def sequence(entry: dict) -> str:
    return " -> ".join(short(n.clean_iri) for n in plan_nodes(entry["plan"]))


def render(outcome: PlanningOutcome, details: bool = False, top: int | None = None) -> str:
    req = outcome.request
    lines: List[str] = []
    lines.append(f"Request:      {req.capability}")
    lines.append(f"Process:      {req.process or '(no process filter)'}")
    lines.append(f"Inputs:       {', '.join(short(t) for t in req.known_inputs) or '-'}")
    lines.append(f"Wanted:       {', '.join(short(t) for t in req.wanted_outputs)}")
    if req.required_quality:
        lines.append("Quality:      " + ", ".join(
            f"{q.criterion_type} {q.logic_interpretation} {num(q.value)}" + (f" (weight {q.weight:g})" if q.weight != 1.0 else "")
            for q in req.required_quality))
    p = outcome.parameters
    lines.append(f"Scoring:      alpha_under={p.alpha_under:g}, s_max={p.s_max:g}, delta={p.delta:g}, "
                 f"tie-breaker exponent={p.tie_breaker_weight:g}")
    lines.append(f"Simulations:  {len(outcome.simulations)} considered")
    lines.append(f"Result:       {outcome.result_type}, {len(outcome.raw_plans)} plans, "
                 f"{len(outcome.ranked)} distinct sequences, {outcome.seconds:.1f} s")
    lines.append("")
    if not outcome.ranked:
        lines.append("No simulation sequence found.")
        return "\n".join(lines)
    ranked = outcome.ranked[:top] if top else outcome.ranked
    lines.append(f"{'Rank':>4}  {'Score':>9}  {'Meets':<5}  Sequence (in execution order)")
    lines.append("-" * 100)
    for e in ranked:
        ev = e["evaluation"]
        lines.append(f"{e['rank']:>4}  {pct(ev['overallScore']):>9}  {'yes' if ev['meetsRequirements'] else 'no':<5}  {sequence(e)}")
    if details:
        for e in ranked:
            ev = e["evaluation"]
            lines.append("")
            lines.append(f"Rank {e['rank']}: {sequence(e)}")
            lines.append(f"  {'Criterion':<16}{'Target':>8}{'Actual':>8}{'Score':>10}")
            for c in ev["criteria"]:
                w = f"  (weight {c['weight']:g})" if c["weight"] != 1.0 else ""
                lines.append(f"  {c['criterion']:<16}{num(c['requiredValue']):>8}{num(c['producedValue']):>8}"
                             f"{pct(c['score']):>10}  {'Meets' if c['meets'] else 'Fails'}{w}")
            if ev["efficiencyTieBreaker"] is not None:
                lines.append(f"  {'Efficiency':<16}{'':>8}{'':>8}{pct(ev['efficiencyTieBreaker']):>10}")
            lines.append(f"  {'Overall score':<16}{'':>8}{'':>8}{pct(ev['overallScore']):>10}")
    return "\n".join(lines)
