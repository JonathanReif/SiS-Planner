"""Export of planned simulation sequences as executable workflow description (FMU based).

The FMU information is modelled with existing terms of VDI 3633 and DIN EN 61360 only:

    VDI3633:SimulationEnvironment --VDI3633:hasModel--> VDI3633:Model (the FMU)
    VDI3633:Model --DINEN61360:has_Data_Element--> DINEN61360:Data_Element
        --DINEN61360:has_Type_Description--> FMUModelName_TD | FMUGuid_TD | FMUFileName_TD | FMUPath_TD
        --DINEN61360:has_Instance_Description--> DINEN61360:String with DINEN61360:Value "..."

The type descriptions are matched by their local name, so they may live in any namespace.
The name of an input or output parameter of the FMU (variable name in the modelDescription.xml)
is the rdfs:label of the VDI3633:InputData / VDI3633:SimulationResultData individual of the run,
otherwise its local name.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from rdflib import Graph, URIRef
from rdflib.namespace import RDFS

from .evaluation import local_name, plan_nodes
from .translate import SimulationDescription, data_elements, type_description
from .vocab import DINEN61360, VDI3633

FMU_FIELDS = {"FMUModelName_TD": "modelName", "FMUGuid_TD": "guid",
              "FMUFileName_TD": "fileName", "FMUPath_TD": "path"}


def _text(g: Graph, de) -> Optional[str]:
    for idesc in g.objects(de, DINEN61360.has_Instance_Description):
        value = g.value(idesc, DINEN61360.Value)
        if value is not None:
            return str(value)
    return None


def fmu_of(g: Graph, environment: URIRef) -> Optional[dict]:
    """FMU description of a simulation environment, or None if it has no VDI3633:hasModel."""
    model = g.value(environment, VDI3633.hasModel)
    if model is None:
        return None
    fmu: Dict[str, Optional[str]] = {"model": str(model), **{f: None for f in FMU_FIELDS.values()}}
    for de in data_elements(g, model):
        td = type_description(g, de)
        field = FMU_FIELDS.get(local_name(str(td))) if td is not None else None
        if field:
            fmu[field] = _text(g, de)
    return fmu


def _parameter(g: Graph, datum: URIRef) -> dict:
    tds = [type_description(g, de) for de in data_elements(g, datum)]
    td = next((t for t in tds if t is not None), None)
    label = g.value(datum, RDFS.label)
    return {"iri": str(datum), "name": str(label) if label is not None else local_name(str(datum)),
            "typeDescription": str(td) if td is not None else None}


def workflow(entry: dict, by_capability: Dict[str, SimulationDescription], g: Graph,
             known_inputs: List[str]) -> dict:
    """Workflow of one ranked sequence: steps in execution order with FMU and data flow."""
    steps, produced = [], {}   # type description -> (position, step output parameter, fmu)
    for position, node in enumerate(plan_nodes(entry["plan"]), 1):
        s = by_capability[node.clean_iri]
        fmu = fmu_of(g, s.environment)
        inputs = []
        for d in s.inputs:
            p = _parameter(g, d)
            origin = produced.get(p["typeDescription"])
            if origin is not None:
                pos, out, src_fmu = origin
                p["source"] = {"kind": "step", "position": pos, "simulation": steps[pos - 1]["simulation"],
                               "parameter": out["name"], "fmuGuid": src_fmu["guid"] if src_fmu else None}
            elif p["typeDescription"] in known_inputs:
                p["source"] = {"kind": "request"}
            else:
                p["source"] = {"kind": "unresolved"}
            inputs.append(p)
        outputs = [_parameter(g, d) for d in s.outputs]
        steps.append({
            "position": position,
            "planStep": node.step_index,
            "simulation": str(s.simulation),
            "simulationRun": str(s.run),
            "simulationEnvironment": str(s.environment),
            "capability": {"iri": str(s.capability), "name": local_name(str(s.capability))},
            "fmu": fmu,
            "inputs": inputs,
            "outputs": outputs,
        })
        for out in outputs:
            produced[out["typeDescription"]] = (position, out, fmu)
    ev = entry["evaluation"]
    return {"rank": entry["rank"], "overallScore": ev["overallScore"],
            "meetsRequirements": ev["meetsRequirements"], "steps": steps}


def workflows_json(outcome, top: Optional[int] = None) -> dict:
    """Workflow description of the ranked sequences of a planning outcome (best first)."""
    req = outcome.request
    by_capability = {str(s.capability): s for s in outcome.simulations}
    known = [str(t) for t in req.known_inputs]
    ranked = outcome.ranked[:top] if top else outcome.ranked
    return {
        "request": {"requiredCapability": str(req.capability),
                    "process": str(req.process) if req.process else None},
        "workflows": [workflow(e, by_capability, outcome.source, known) for e in ranked],
    }
