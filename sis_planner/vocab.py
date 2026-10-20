"""Namespaces used by the SiS model and the planning core."""
from rdflib import Namespace

SIS = Namespace("http://www.semanticweb.org/reif/ontologies/SiS#")
VDI3633 = Namespace("http://www.semanticweb.org/reif/ontologies/VDI3633#")
VDI3682 = Namespace("http://www.w3id.org/hsu-aut/VDI3682#")
DINEN61360 = Namespace("http://www.w3id.org/hsu-aut/DINEN61360#")
CSS = Namespace("http://www.w3id.org/hsu-aut/css#")
CASK = Namespace("http://www.w3id.org/hsu-aut/cask#")
MATH = Namespace("http://openmath.org/vocab/math#")

NS_PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX SiS: <http://www.semanticweb.org/reif/ontologies/SiS#>
PREFIX VDI3633: <http://www.semanticweb.org/reif/ontologies/VDI3633#>
PREFIX VDI3682: <http://www.w3id.org/hsu-aut/VDI3682#>
PREFIX DINEN61360: <http://www.w3id.org/hsu-aut/DINEN61360#>
PREFIX CSS: <http://www.w3id.org/hsu-aut/css#>
PREFIX CaSk: <http://www.w3id.org/hsu-aut/cask#>
PREFIX math: <http://openmath.org/vocab/math#>
"""


def bind_prefixes(graph) -> None:
    for prefix, ns in (("SiS", SIS), ("VDI3633", VDI3633), ("VDI3682", VDI3682), ("DINEN61360", DINEN61360),
                       ("CSS", CSS), ("CaSk", CASK), ("math", MATH)):
        graph.bind(prefix, ns)
