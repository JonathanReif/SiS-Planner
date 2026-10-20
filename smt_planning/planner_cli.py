from typing import Optional
from smt_planning import __app_name__, __version__
from smt_planning.smt.cask_to_smt import CaskadePlanner
import typer

app = typer.Typer()

def _version_callback(value: bool) -> None:
	if value:
		typer.echo(f"{__app_name__} v{__version__}")
		raise typer.Exit()

@app.command()
def plan_from_file(
	ontology_file: str = typer.Argument(
		help="Path to your ontology that is used for generating the planning problem",
	),
	required_capability_iri: str = typer.Argument(
		help="IRI of the required capability to plan for.",
	),
	max_happenings: int = typer.Option(
		20,
		"--max-happenings",
		"-mh",
		help="Maximum number of happenings to consider (default: 20)",
	),
	problem_file: str = typer.Option(
		None,
		"--problem-file",
		"-problem",
		help="Path to where the generated problem will be stored (default: None)",
	),
	model_file: str = typer.Option(
		None,
		"--model-file",
		"-model",
		help="Path to where the model file will be stored after solving (default: None)",
	),
	plan_file: str = typer.Option(
		None,
		"--plan-file",
		"-plan",
		help="Path to where the plan file will be stored after solving and transformation (default: None)",
	),
	find_all_solutions: bool = typer.Option(
		False,
		"--find-all-solutions",
		"-all",
		help="Find all possible solutions instead of just one (default: False)",
	),
) -> None:
	planner = CaskadePlanner(required_capability_iri)
	planner.with_file_query_handler(ontology_file)
	result = planner.cask_to_smt(max_happenings, problem_file, model_file, plan_file, find_all_solutions)
	result_json = result.to_json()
	print(result_json)


@app.command()
def plan_from_endpoint(
	endpoint_url: str = typer.Argument(
		help="URL of the SPARQL endpoint with all the capabilities",
	),
	required_capability_iri: str = typer.Argument(
		help="IRI of the required capability to plan for.",
	),
	max_happenings: int = typer.Option(
		20,
		"--max-happenings",
		"-mh",
		help="Maximum number of happenings to consider (default: 20)",
	),
	problem_file: str = typer.Option(
		None,
		"--problem-file",
		"-problem",
		help="Path to where the generated problem will be stored (default: None)",
	),
	model_file: str = typer.Option(
		None,
		"--model-file",
		"-model",
		help="Path to where the model file will be stored after solving (default: None)",
	),
	plan_file: str = typer.Option(
		None,
		"--plan-file",
		"-plan",
		help="Path to where the plan file will be stored after solving and transformation (default: None)",
	),
	find_all_solutions: bool = typer.Option(
		False,
		"--find-all-solutions",
		"-all",
		help="Find all possible solutions instead of just one (default: False)",
	),
) -> None:
	planner = CaskadePlanner(required_capability_iri)
	planner.with_endpoint_query_handler(endpoint_url)
	result = planner.cask_to_smt(max_happenings, problem_file, model_file, plan_file, find_all_solutions)
	result_json = result.to_json()
	print(result_json)



@app.callback()
def main(
	version: Optional[bool] = typer.Option(
		None,
		"--version",
		"-v",
		help="Show the application's version and exit.",
		callback=_version_callback,
		is_eager=True,
	)
) -> None:
	return

def run():
	app()

if __name__ == "__main__":
	run()
