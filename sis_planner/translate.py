"""Translation of SiS descriptions into the planning view of the CaSkade planning core.

Input are simulation descriptions following the SiS model and a request (see ``Request``):

    VDI3633:Simulation  --SiS:isSimulationFor-->        process of the production system
                        --VDI3633:comprisesExperiment--> VDI3633:SimulationExperiment
    SimulationExperiment --VDI3633:hasSimulationRun-->   VDI3633:SimulationRun
    SimulationRun --CSS:requiresCapability-->            capability
                  --VDI3633:isExecutedWith-->            VDI3633:SimulationEnvironment
                  --VDI3633:hasInputData-->              VDI3633:InputData
                  --VDI3633:hasSimulationResultData-->   VDI3633:SimulationResultData
    SimulationEnvironment --CSS:providesCapability-->    capability
                          --SiS:hasQualityCriteria-->    SiS:QualityCriteria
    data / quality criteria / influences --SiS:hasDataElement--> DINEN61360:Data_Element
    InputData --SiS:hasInfluence--> SiS:Influence --SiS:hasInfluenceOn--> SiS:QualityCriteria
                                                  --SiS:isInfluenceFor--> SimulationRun

The planning view is the encoding the CaSkade planning core works on: every simulation run
becomes a VDI3682 process operator whose inputs
and outputs are characterised by DINEN61360 instance descriptions. The availability of a datum
is encoded as the value 1000 (0 = not available). The initial state of the planning problem
is derived from the loaded knowledge base on every run: each type description that occurs as
input or output of a selected simulation run is initialised with 0, unless it is a known input
of the request (1000).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS

from .evaluation import RequiredQuality, local_name
from .vocab import CASK, CSS, DINEN61360, MATH, SIS, VDI3633, VDI3682, bind_prefixes

AVAILABLE = 1000
NOT_AVAILABLE = 0
DEFAULT_INFLUENCE_TD = URIRef(str(SIS) + "influenceScore_TD")
# Weight w_q of a required quality criterion (optional, default 1.0)
SIS_WEIGHT = SIS.weight


class TranslationError(ValueError):
    pass


# ----------------------------------------------------------------------------- helpers

def data_elements(g: Graph, subject) -> List[URIRef]:
    """Data elements of a SiS entity (SiS:hasDataElement or DINEN61360:has_Data_Element)."""
    des = list(g.objects(subject, SIS.hasDataElement)) + list(g.objects(subject, DINEN61360.has_Data_Element))
    return list(dict.fromkeys(des))


def type_description(g: Graph, de) -> Optional[URIRef]:
    return next(iter(g.objects(de, DINEN61360.has_Type_Description)), None)


def instance_value(g: Graph, de) -> Optional[float]:
    for idesc in g.objects(de, DINEN61360.has_Instance_Description):
        for v in g.objects(idesc, DINEN61360.Value):
            return float(v)
    return None


def instance_literal(g: Graph, de, prop) -> Optional[str]:
    for idesc in g.objects(de, DINEN61360.has_Instance_Description):
        for v in g.objects(idesc, prop):
            return str(v)
    return None


def single(g: Graph, s, p, what: str):
    values = list(g.objects(s, p))
    if not values:
        raise TranslationError(f"{what}: no value for {local_name(str(p))} of {s}")
    return values[0]


def _ns_of(iri: str) -> str:
    return iri[: iri.rfind("#") + 1] if "#" in iri else iri.rstrip("/") + "/"


# ----------------------------------------------------------------------------- request

@dataclass
class Request:
    """A planning request described with SiS (a not yet existing simulation)."""
    simulation: URIRef
    process: Optional[URIRef]
    run: URIRef
    capability: URIRef
    known_inputs: List[URIRef] = field(default_factory=list)       # type descriptions
    wanted_outputs: List[URIRef] = field(default_factory=list)     # type descriptions
    required_quality: List[RequiredQuality] = field(default_factory=list)

    @classmethod
    def from_graph(cls, g: Graph) -> "Request":
        caps = list(g.subjects(RDF.type, CASK.RequiredCapability))
        if len(caps) != 1:
            raise TranslationError(f"The request must contain exactly one CaSk:RequiredCapability (found {len(caps)})")
        cap = caps[0]
        runs = list(g.subjects(CSS.requiresCapability, cap))
        if len(runs) != 1:
            raise TranslationError("Exactly one VDI3633:SimulationRun must require the requested capability")
        run = runs[0]
        experiment = next(iter(g.subjects(VDI3633.hasSimulationRun, run)), None)
        simulation = next(iter(g.subjects(VDI3633.comprisesExperiment, experiment)), None) if experiment else None
        process = next(iter(g.objects(simulation, SIS.isSimulationFor)), None) if simulation else None

        def tds(prop) -> List[URIRef]:
            out = []
            for d in g.objects(run, prop):
                for de in data_elements(g, d):
                    td = type_description(g, de)
                    if td is None:
                        raise TranslationError(f"Data element {de} of {d} has no type description")
                    out.append(td)
            return list(dict.fromkeys(out))

        required = []
        rq_nodes = set(g.subjects(RDF.type, SIS.RequiredQuality))
        for rq in sorted(rq_nodes, key=str):
            weight = g.value(rq, SIS_WEIGHT)
            for de in data_elements(g, rq):
                td, value = type_description(g, de), instance_value(g, de)
                if td is None or value is None:
                    raise TranslationError(f"Required quality {rq} needs a type description and a value")
                logic = instance_literal(g, de, DINEN61360.Logic_Interpretation) or ">="
                required.append(RequiredQuality(str(td), value, logic, float(weight) if weight is not None else 1.0))
        req = cls(simulation or run, process, run, cap, tds(VDI3633.hasInputData), tds(VDI3633.hasSimulationResultData), required)
        if not req.wanted_outputs:
            raise TranslationError("The request run has no VDI3633:hasSimulationResultData")
        return req


# ----------------------------------------------------------------------------- simulations

@dataclass
class SimulationDescription:
    simulation: URIRef
    process: Optional[URIRef]
    run: URIRef
    environment: URIRef
    capability: URIRef
    inputs: List[URIRef]
    outputs: List[URIRef]


def find_simulations(g: Graph, exclude: Set[URIRef] = frozenset()) -> List[SimulationDescription]:
    sims = []
    for sim in sorted(set(g.subjects(RDF.type, VDI3633.Simulation)), key=str):
        if sim in exclude:
            continue
        process = next(iter(g.objects(sim, SIS.isSimulationFor)), None)
        for exp in g.objects(sim, VDI3633.comprisesExperiment):
            for run in g.objects(exp, VDI3633.hasSimulationRun):
                env = next(iter(g.objects(run, VDI3633.isExecutedWith)), None)
                cap = next(iter(g.objects(run, CSS.requiresCapability)), None)
                if env is None or cap is None:
                    raise TranslationError(f"Simulation run {run} needs VDI3633:isExecutedWith and CSS:requiresCapability")
                if (env, CSS.providesCapability, cap) not in g:
                    raise TranslationError(f"Environment {env} does not provide the capability {cap} required by {run}")
                sims.append(SimulationDescription(sim, process, run, env, cap,
                                                  sorted(g.objects(run, VDI3633.hasInputData), key=str),
                                                  sorted(g.objects(run, VDI3633.hasSimulationResultData), key=str)))
    return sims


def select_for_process(sims: List[SimulationDescription], process: Optional[URIRef]) -> List[SimulationDescription]:
    """Process filter: only simulations that are bound to the requested process (SiS:isSimulationFor)."""
    if process is None:
        return sims
    return [s for s in sims if s.process == process]


# ----------------------------------------------------------------------------- planning view

class ViewBuilder:
    def __init__(self, source: Graph) -> None:
        self.src = source
        self.view = Graph()
        bind_prefixes(self.view)
        self.io_types: Set[URIRef] = set()
        # inputs that only exist in the planning encoding (not part of the data flow)
        self.auxiliary: Set[URIRef] = set()
        # instance descriptions referenced by capability constraints are used as planning variables
        self.id_override: Dict[URIRef, URIRef] = {}
        # OpenMath variables of interdependencies -> type description of the referenced datum
        self.variable_types: Dict[str, str] = {}

    def add(self, s, p, o) -> None:
        self.view.add((s, p, o))

    # --------------------------------------------------------------- OpenMath expressions

    def data_element_of(self, instance_description) -> Optional[URIRef]:
        return next(iter(self.src.subjects(DINEN61360.has_Instance_Description, instance_description)), None)

    def openmath(self, node, variables: List) -> None:
        """Copy an OpenMath expression (math:Application with nested arguments) into the view.

        Arguments that are instance descriptions of data elements are collected in ``variables``.
        """
        g = self.src
        operator = next(iter(g.objects(node, MATH.operator)), None)
        if operator is None:
            raise TranslationError(f"OpenMath application {node} has no math:operator")
        self.add(node, RDF.type, MATH.Application)
        self.add(node, MATH.operator, operator)
        args = next(iter(g.objects(node, MATH.arguments)), None)
        if args is None:
            raise TranslationError(f"OpenMath application {node} has no math:arguments")
        self.add(node, MATH.arguments, args)
        cell = args
        while cell != RDF.nil:
            first, rest = g.value(cell, RDF.first), g.value(cell, RDF.rest)
            if first is None or rest is None:
                raise TranslationError(f"Malformed argument list of {node}")
            self.add(cell, RDF.first, first)
            self.add(cell, RDF.rest, rest)
            if (first, MATH.operator, None) in g:
                self.openmath(first, variables)
            elif (first, MATH.value, None) in g:
                self.add(first, RDF.type, MATH.Literal)
                self.add(first, MATH.value, g.value(first, MATH.value))
            elif self.data_element_of(first) is not None:
                self.add(first, RDF.type, MATH.Variable)
                variables.append(first)
            else:
                raise TranslationError(f"Argument {first} of {node} is neither an application, a literal "
                                       "(math:value) nor an instance description of a data element")
            cell = rest

    def capability_constraints(self, s: SimulationDescription) -> None:
        """Pass CSS:isRestrictedBy constraints of a provided capability to the planning core."""
        g = self.src
        run_des = {de for d in s.inputs + s.outputs for de in data_elements(g, d)}
        for constraint in g.objects(s.capability, CSS.isRestrictedBy):
            variables: List = []
            self.openmath(constraint, variables)
            self.add(s.capability, CSS.isRestrictedBy, constraint)
            self.add(constraint, RDF.type, CSS.CapabilityConstraint)
            for var in variables:
                de = self.data_element_of(var)
                if de not in run_des:
                    raise TranslationError(f"Constraint {constraint} of {s.capability} refers to {var}, "
                                           "which is not an instance description of an input or result datum of the run")
                self.id_override[de] = var

    def instance(self, de: URIRef, iri: URIRef, dtype, value, goal: str, characterized=None) -> None:
        self.add(de, RDF.type, DINEN61360.Data_Element)
        self.add(de, DINEN61360.has_Instance_Description, iri)
        self.add(iri, RDF.type, DINEN61360.Instance_Description)
        self.add(iri, RDF.type, dtype)
        self.add(iri, DINEN61360.Logic_Interpretation, Literal("="))
        self.add(iri, DINEN61360.Value, Literal(value))
        self.add(iri, DINEN61360.Expression_Goal, Literal(goal))
        if characterized is not None:
            self.add(characterized, VDI3682.isCharacterizedBy, iri)

    def information(self, process: URIRef, rel, info: URIRef, de: URIRef, td: URIRef, value, goal: str,
                    dtype=DINEN61360.Integer) -> None:
        self.add(process, rel, info)
        self.add(info, RDF.type, VDI3682.Information)
        self.add(info, DINEN61360.has_Data_Element, de)
        self.add(de, DINEN61360.has_Type_Description, td)
        self.add(td, RDF.type, DINEN61360.Type_Description)
        self.instance(de, self.id_override.get(de, URIRef(str(de) + "_ID")), dtype, value, goal, characterized=info)
        self.io_types.add(td)

    def simulation(self, s: SimulationDescription) -> None:
        g, run = self.src, s.run
        self.add(run, RDF.type, VDI3682.ProcessOperator)
        self.add(run, CSS.requiresCapability, s.capability)
        self.add(s.capability, RDF.type, CASK.ProvidedCapability)
        self.add(s.capability, RDF.type, CSS.Capability)
        self.add(s.environment, CSS.providesCapability, s.capability)
        for label in g.objects(s.simulation, RDFS.label):
            self.add(s.capability, RDFS.label, label)
        if s.process is not None:
            self.add(s.simulation, SIS.isSimulationFor, s.process)
        self.capability_constraints(s)
        # inputs: datum must be available (Requirement 1000)
        for d in s.inputs:
            for de in data_elements(g, d):
                self.information(run, VDI3682.hasInput, d, de, self._td(de, d), AVAILABLE, "Requirement")
            for inf in g.objects(d, SIS.hasInfluence):
                if (inf, SIS.isInfluenceFor, run) in g:
                    self.add(d, SIS.hasInfluence, inf)
                    self.influence(run, inf)
        # outputs: datum becomes available (Assurance 1000), and must not be available before
        for d in s.outputs:
            for de in data_elements(g, d):
                td = self._td(de, d)
                self.information(run, VDI3682.hasOutput, d, de, td, AVAILABLE, "Assurance")
                req_info = URIRef(_ns_of(str(d)) + "Required" + local_name(str(d)))
                req_de = URIRef(_ns_of(str(de)) + "Required" + local_name(str(de)))
                self.information(run, VDI3682.hasInput, req_info, req_de, td, NOT_AVAILABLE, "Requirement")
                self.auxiliary.add(req_de)
        # quality criteria of the environment
        for qc in g.objects(s.environment, SIS.hasQualityCriteria):
            self.add(s.environment, SIS.hasQualityCriteria, qc)
            self.add(qc, RDF.type, SIS.QualityCriteria)
            self.quality_criterion(qc)

    def _td(self, de, owner) -> URIRef:
        td = type_description(self.src, de)
        if td is None:
            raise TranslationError(f"Data element {de} of {owner} has no type description")
        return td

    def quality_criterion(self, qc: URIRef) -> None:
        g = self.src
        des = data_elements(g, qc)
        if des:
            for de in des:
                td, value = type_description(g, de), instance_value(g, de)
                if td is None or value is None:
                    raise TranslationError(f"Quality criterion {qc} needs a type description and a value")
                self.add(qc, DINEN61360.has_Data_Element, de)
                self.add(de, DINEN61360.has_Type_Description, td)
                self.instance(de, next(iter(g.objects(de, DINEN61360.has_Instance_Description))),
                              DINEN61360.Real, value, "Assurance")
            return
        # alternative modelling with SiS data properties
        value = next(iter(g.objects(qc, SIS.qualityCriterionValue)), None)
        ctype = next(iter(g.objects(qc, SIS.qualityCriterionType)), None)
        if value is None or ctype is None:
            raise TranslationError(f"Quality criterion {qc} has neither a data element nor SiS:qualityCriterionValue/Type")
        td = URIRef(str(ctype)) if ":" in str(ctype) else URIRef(_ns_of(str(qc)) + str(ctype))
        de = URIRef(str(qc) + "_DE")
        self.add(qc, DINEN61360.has_Data_Element, de)
        self.add(de, DINEN61360.has_Type_Description, td)
        self.instance(de, URIRef(str(qc) + "_ID"), DINEN61360.Real, float(value), "Assurance")

    def influence(self, run: URIRef, inf: URIRef) -> None:
        g = self.src
        self.add(inf, SIS.isInfluenceFor, run)
        for qc in g.objects(inf, SIS.hasInfluenceOn):
            self.add(inf, SIS.hasInfluenceOn, qc)
        for t in g.objects(inf, RDF.type):
            self.add(inf, RDF.type, t)
        des = data_elements(g, inf)
        if (inf, RDF.type, SIS.Interdependency) in g:
            self.interdependency(inf, des)
            return
        if des:
            de = des[0]
            value = instance_value(g, de)
            td = type_description(g, de) or DEFAULT_INFLUENCE_TD
        else:
            value = next(iter(g.objects(inf, SIS.influenceValue)), None)
            de, td = URIRef(str(inf) + "_DE"), DEFAULT_INFLUENCE_TD
        if value is None:
            raise TranslationError(f"Influence {inf} has no value")
        self.information(run, VDI3682.hasInput, inf, de, td, float(value), "Actual_Value", DINEN61360.Real)
        self.auxiliary.add(de)

    def interdependency(self, inf: URIRef, des: List[URIRef]) -> None:
        """Influence given as OpenMath expression, evaluated with the propagated quality.

        The expression is either the interdependency itself (math:operator / math:arguments) or
        a math:Application linked to its data element with CSS:isRestrictedBy.
        """
        g = self.src
        if (inf, MATH.operator, None) in g:
            root = inf
        else:
            root = next((a for de in des for a in g.objects(de, CSS.isRestrictedBy)), None)
        if root is None:
            raise TranslationError(f"Interdependency {inf} has no OpenMath expression")
        variables: List = []
        self.openmath(root, variables)
        de = des[0] if des else URIRef(str(inf) + "_DE")
        self.add(inf, DINEN61360.has_Data_Element, de)
        self.add(de, RDF.type, SIS.Interdependency)
        self.add(de, CSS.isRestrictedBy, root)
        for var in variables:
            td = type_description(g, self.data_element_of(var))
            if td is not None:
                self.variable_types[str(var)] = str(td)

    def request(self, req: Request) -> None:
        run, cap = req.run, req.capability
        self.add(run, RDF.type, VDI3682.ProcessOperator)
        self.add(cap, RDF.type, CASK.RequiredCapability)
        self.add(cap, RDF.type, CSS.Capability)
        self.add(run, CSS.requiresCapability, cap)
        ns = _ns_of(str(cap))
        inp, out = URIRef(ns + "InputInformation"), URIRef(ns + "OutputInformation")
        self.add(run, VDI3682.hasInput, inp)
        self.add(run, VDI3682.hasOutput, out)
        self.add(inp, RDF.type, VDI3682.Information)
        self.add(out, RDF.type, VDI3682.Information)
        known = set(req.known_inputs)
        # initial state, derived from the knowledge base
        for td in sorted(self.io_types | known | set(req.wanted_outputs), key=str):
            de = URIRef(ns + "init_" + local_name(str(td)) + "_DE")
            self.add(inp, DINEN61360.has_Data_Element, de)
            self.add(de, DINEN61360.has_Type_Description, td)
            self.instance(de, URIRef(ns + "init_" + local_name(str(td)) + "_ID"), DINEN61360.Integer,
                          AVAILABLE if td in known else NOT_AVAILABLE, "Actual_Value", characterized=inp)
        # goal
        for td in req.wanted_outputs:
            de = URIRef(ns + "goal_" + local_name(str(td)) + "_DE")
            self.add(out, DINEN61360.has_Data_Element, de)
            self.add(de, DINEN61360.has_Type_Description, td)
            self.instance(de, URIRef(ns + "goal_" + local_name(str(td)) + "_ID"), DINEN61360.Integer,
                          AVAILABLE, "Requirement", characterized=out)


@dataclass
class ViewInfo:
    """Information about the planning view needed for the evaluation."""
    auxiliary: Set[URIRef]
    variable_types: Dict[str, str]


def build_view(knowledge: Graph, request_graph: Graph, use_process_filter: bool = True):
    """Return (planning view, request, selected simulations, ViewInfo)."""
    req = Request.from_graph(request_graph)
    merged = knowledge + request_graph
    sims = find_simulations(merged, exclude={req.simulation})
    selected = select_for_process(sims, req.process) if use_process_filter else sims
    if not selected:
        raise TranslationError("No simulation in the knowledge base is bound to the requested process")
    builder = ViewBuilder(merged)
    for s in selected:
        builder.simulation(s)
    builder.request(req)
    return builder.view, req, selected, ViewInfo(builder.auxiliary, builder.variable_types)
