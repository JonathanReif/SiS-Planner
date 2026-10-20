"""Command line interface of the SiS-Planner."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional

import typer

from .loader import load_endpoint, load_files
from .translate import Request, TranslationError, build_view, find_simulations, select_for_process

app = typer.Typer(add_completion=False, help="Capability-based planning of simulation sequences from SiS descriptions.")


def _knowledge(kb: Optional[List[Path]], endpoint: Optional[str], user: Optional[str], password: Optional[str]):
    if bool(kb) == bool(endpoint):
        raise typer.BadParameter("Specify the knowledge base either with --kb or with --endpoint.")
    if endpoint:
        typer.echo(f"Loading descriptions from {endpoint} ...", err=True)
        return load_endpoint(endpoint, user=user, password=password)
    return load_files(kb)


@app.command()
def plan(
    request: Path = typer.Argument(..., exists=True, help="Request (SiS description of the wanted simulation, Turtle)."),
    kb: Optional[List[Path]] = typer.Option(None, "--kb", help="File or directory with SiS descriptions (repeatable)."),
    endpoint: Optional[str] = typer.Option(None, "--endpoint", help="SPARQL endpoint, e.g. http://localhost:7200/repositories/sis"),
    user: Optional[str] = typer.Option(None, help="User for the SPARQL endpoint."),
    password: Optional[str] = typer.Option(None, help="Password for the SPARQL endpoint."),
    json_out: Optional[Path] = typer.Option(None, "--json", help="Write the complete result as JSON."),
    details: bool = typer.Option(False, "--details", "-d", help="Show the evaluation per quality criterion."),
    top: Optional[int] = typer.Option(None, help="Show only the best N sequences."),
    max_happenings: int = typer.Option(20, help="Upper bound for the number of planning steps."),
    no_process_filter: bool = typer.Option(False, "--no-process-filter", help="Consider simulations of all processes."),
    save_view: Optional[Path] = typer.Option(None, help="Write the generated planning view (Turtle) for inspection."),
    verbose: bool = typer.Option(False, "--verbose", help="Show the output of the planning core."),
    alpha_under: float = typer.Option(0.1, help="Score of a criterion that misses its target."),
    s_max: float = typer.Option(1.5, help="Upper bound of the bonus for over-fulfilment."),
    delta: float = typer.Option(1.0, help="Growth factor of the bonus for over-fulfilment."),
    tie_breaker_weight: float = typer.Option(0.5, help="Exponent of the implicit efficiency tie-breaker."),
):
    """Plan simulation sequences for a request and rank them by the required quality."""
    from .evaluation import ScoringParameters
    from .pipeline import plan as run
    from .report import render

    sys.stdout.reconfigure(encoding="utf-8")
    knowledge = _knowledge(kb, endpoint, user, password)
    params = ScoringParameters(alpha_under, s_max, delta, tie_breaker_weight)
    try:
        outcome = run(knowledge, load_files([request]), max_happenings, not no_process_filter, verbose, params)
    except TranslationError as exc:
        typer.echo(f"Error in the descriptions: {exc}", err=True)
        raise typer.Exit(2)
    typer.echo(render(outcome, details, top))
    if json_out:
        json_out.write_text(json.dumps(outcome.to_json(), indent=2, ensure_ascii=False), encoding="utf-8")
        typer.echo(f"\nJSON written to {json_out}")
    if save_view:
        outcome.view.serialize(save_view, format="turtle")
        typer.echo(f"Planning view written to {save_view}")


@app.command()
def check(
    request: Path = typer.Argument(..., exists=True, help="Request (Turtle)."),
    kb: Optional[List[Path]] = typer.Option(None, "--kb"),
    endpoint: Optional[str] = typer.Option(None, "--endpoint"),
    user: Optional[str] = typer.Option(None),
    password: Optional[str] = typer.Option(None),
):
    """Check request and knowledge base without planning."""
    from .report import short

    sys.stdout.reconfigure(encoding="utf-8")
    knowledge = _knowledge(kb, endpoint, user, password)
    try:
        req = Request.from_graph(load_files([request]))
        sims = find_simulations(knowledge, exclude={req.simulation})
        selected = select_for_process(sims, req.process)
        build_view(knowledge, load_files([request]))
    except TranslationError as exc:
        typer.echo(f"Error in the descriptions: {exc}", err=True)
        raise typer.Exit(2)
    typer.echo(f"Request:      {req.capability}")
    typer.echo(f"Process:      {req.process}")
    typer.echo(f"Inputs:       {', '.join(short(t) for t in req.known_inputs)}")
    typer.echo(f"Outputs:      {', '.join(short(t) for t in req.wanted_outputs)}")
    for q in req.required_quality:
        typer.echo(f"Quality:      {q.criterion_type} {q.logic_interpretation} {q.value} (weight {q.weight:g})")
    typer.echo(f"Simulations:  {len(sims)} in the knowledge base, {len(selected)} bound to the process")
    for s in sims:
        mark = "+" if s in selected else "-"
        typer.echo(f"  {mark} {short(str(s.simulation))}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
