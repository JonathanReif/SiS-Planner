# SiS-Planner

Capability-based generation of simulation sequences from semantic simulation descriptions.

The SiS-Planner takes simulations described with the
[SiS (Simulation Support) information model](https://github.com/JonathanReif/SiS) and a request
(Required Capability), generates all candidate sequences that produce the required results from
the available data, and ranks them by the required quality. Candidate sequences are generated with
the SMT-based planning core of the [CaSkade-Planner](https://github.com/CaSkade-Automation/CaSkade-Planner)
(`smt_planning/`).

## Installation

Requires Python 3.11 or newer.

```bash
git clone <repository-url> SiS-Planner
cd SiS-Planner
python -m venv .venv
# Windows: .venv\Scripts\activate      Linux/macOS: source .venv/bin/activate
pip install -e .
```

## Usage

```bash
sis-planner plan examples/requests/stress_request.ttl --kb examples/simulations --details
```

```
Rank      Score  Meets  Sequence (in execution order)
   1    188.7 %  yes    Meshing -> LinearFEA
   2     16.5 %  no     Meshing -> SurrogateModel
```

The simulations are read from Turtle files (`--kb`, file or directory) or from a SPARQL endpoint
(`--endpoint http://localhost:7200/repositories/<repo>`, read only). Further options:
`--details` (evaluation per quality criterion), `--json FILE` (complete result),
`--workflow-json FILE` (executable workflow, see below), `--no-process-filter`, `sis-planner check`
(request and considered simulations without planning) and `sis-planner plan --help`. The example
data in `examples/` is fictional.

## Workflow export (FMU)

`--workflow-json FILE` writes the ranked sequences (best first, limited by `--top`) as workflow
description; with `--workflow-json -` the JSON goes to stdout and the report to stderr. Every step
contains the IRIs of simulation, simulation run, environment and capability, the FMU (model name,
GUID, file name, path) and the input and output parameters. Every input names its source: the
request or the output parameter of a preceding step together with that FMU's GUID.

```bash
sis-planner plan examples/requests/cure_request.ttl --kb examples/simulations --top 1 --workflow-json -
```

The FMU is described with existing terms of VDI 3633 and DIN EN 61360 only (see
`examples/simulations/thermal_fe.ttl`):

```turtle
:Environment VDI3633:hasModel :FMU .
:FMU a VDI3633:Model ;
    DINEN61360:has_Data_Element :FMU_Guid_DE .            # likewise model name, file name, path
:FMU_Guid_DE a DINEN61360:Data_Element ;
    DINEN61360:has_Type_Description t:FMUGuid_TD ;        # FMUModelName_TD, FMUFileName_TD, FMUPath_TD
    DINEN61360:has_Instance_Description [ a DINEN61360:Instance_Description, DINEN61360:String ;
                                          DINEN61360:Value "{3f2a8c1e-...}" ] .
:TemperatureField a VDI3633:SimulationResultData ;
    rdfs:label "temperatureField" .                       # variable name in the FMU
```

The type descriptions are matched by their local name (any namespace). Without `VDI3633:hasModel`
the field `fmu` is `null`; without `rdfs:label` the local name of the datum is used as parameter name.

## Request

A request describes the required simulation with the structure of the SiS information model
(see `examples/requests/stress_request.ttl`): a `VDI3633:SimulationRun` that requires a
`CaSk:RequiredCapability`, with

- the manufacturing process (`SiS:isSimulationFor`) for the process-specific filtering,
- the available data (`VDI3633:hasInputData`) and the required data (`VDI3633:hasSimulationResultData`),
- the required quality (`SiS:RequiredQuality` with type description, `DINEN61360:Value` as threshold
  and optionally `SiS:weight` as weight w_q, default 1.0).

The initial state of the planning problem is derived from the loaded simulations on every run.

## Method

1. **Process-specific filtering:** only simulations bound to the requested process via
   `SiS:isSimulationFor` are considered.
2. **Candidate generation:** the simulations are translated into the planning problem of the
   CaSkade planning core. Data are matched by their `DINEN61360:has_Type_Description`, capability
   constraints (`CSS:isRestrictedBy`, OpenMath) are passed on as SMT constraints. All candidate
   sequences with the minimal number of capabilities are enumerated (at most 15).
3. **Quality propagation:** for every required criterion the quality is propagated along the
   sequence, `q_out = max(0, q_int - (q_int - q_in) * f)` for a deficit of an input, with the
   influence factor `f` from `SiS:InfluenceScore`, `SiS:SensitivityIndex` or `SiS:Interdependency`
   (OpenMath expression, evaluated with the propagated quality). With several inputs the largest
   weighted deficit counts, the value of the sequence is the minimum over its final outputs.
   Missing quality criteria and influences count as 1.0.
4. **Evaluation:** weighted product model `Score(Seq) = prod_q f(output_q, target_q)^w_q` with
   `f = alpha_under` if the target is missed, otherwise
   `f = 1 + (s_max - 1) * (1 - exp(-delta * |output - target| / target))`. Without requirements on
   efficiency criteria an implicit efficiency tie-breaker (SimTime, TRL) is applied. Sequences that
   meet all requirements are ranked first.

## Adapting the evaluation

The parameters of the score function and the weights are use-case specific and should be chosen
together with domain experts. The defaults are `alpha_under = 0.1`, `s_max = 1.5`, `delta = 1.0`
and `w_q = 1.0`. The parameters can be set with `--alpha-under`, `--s-max`, `--delta` and
`--tie-breaker-weight`, the weights in the request (`SiS:weight`). Further changes can be made in
`sis_planner/evaluation.py`.

## License

MIT, see `LICENSE`. The planning core in `smt_planning/` is part of the CaSkade-Planner
(MIT License, see `smt_planning/LICENSE`).
