from typing import List, Mapping, Set

from rdflib import Graph, Variable
from rdflib.term import Identifier 

from smt_planning.smt.StateHandler import StateHandler
from smt_planning.dicts.PropertyDictionary import Property
from smt_planning.smt.property_links import get_related_properties
from smt_planning.dicts.CapabilityDictionary import Capability

class CapabilityPair:
	def __init__(self, capability_a: Capability, capability_b: Capability, property: Property) -> None:
		self.capability_a = capability_a
		self.capability_b = capability_b
		self.property = property

def get_related_capabilities(capability_iri:str, property_iri:str) -> List[Capability]:
	# Get all related properties and extract their capabilities
	property_partners = get_related_properties(property_iri)

	# Create a set to get only unique values. We don't want the original cap, that's why its added in the beginning
	related_capability_iris = set()
	related_capability_iris.add(capability_iri)
	for property_partner in property_partners:
		related_capability_iris.add(*property_partner.capability_iris)
	
	# remove cap itself because we only want the related caps
	related_capability_iris.remove(capability_iri)

	# get the capability objects for each entry
	related_capabilities = []
	capability_dictionary = StateHandler().get_capability_dictionary()
	for related_capability_iri in related_capability_iris:
		capability = capability_dictionary.get_capability(related_capability_iri)
		if capability.capability_type == 'http://www.w3id.org/hsu-aut/cask#ProvidedCapability':
			related_capabilities.append(capability)

	return related_capabilities
	
