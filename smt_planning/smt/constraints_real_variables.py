from z3 import Implies, Not, And
from typing import List

from smt_planning.smt.StateHandler import StateHandler
from smt_planning.dicts.PropertyDictionary import Property
from smt_planning.dicts.CapabilityDictionary import Capability
from smt_planning.smt.property_links import get_related_properties
from smt_planning.smt.capability_links import get_related_capabilities

def get_variable_constraints(happenings: int, event_bound: int) -> List:

	stateHandler = StateHandler()
	property_dictionary = stateHandler.get_property_dictionary()
	capability_dictionary = stateHandler.get_capability_dictionary()
	
	constraints = []
	properties = property_dictionary.provided_properties.values()
	for original_property in properties:
		if original_property.data_type != "http://www.w3id.org/hsu-aut/DINEN61360#Real" and original_property.data_type != "http://www.w3id.org/hsu-aut/DINEN61360#Integer": continue
		
		# Get all capabilities directly or indirectly influencing current property
		property_capability_iris = original_property.capability_iris
		capabilities = [capability_dictionary.get_provided_capability(capabilit_iri) for capabilit_iri in property_capability_iris]
		
		related_capabilities: List[Capability] = []
		for capability_iri in property_capability_iris:
			current_cap_related_capabilities = get_related_capabilities(capability_iri, original_property.iri)
			related_capabilities.extend(current_cap_related_capabilities)
		
		all_capabilities = [*capabilities, *related_capabilities]
		
		# Get all properties (this one and its related ones)
		related_properties = get_related_properties(original_property.iri)
		all_properties = [original_property, *related_properties]

		all_capabilities_with_numeric_influence: List[Capability] = []
		for capability in all_capabilities:
			for property in all_properties:
				if capability.has_effect_on_property(property) or has_effect_on_related_prop_in_same_cap(property, capability):
					# If there is an influence, we add the cap and continue to the next
					all_capabilities_with_numeric_influence.append(capability)
					break	


		for happening in range(happenings):
			prop_start = original_property.occurrences[happening][0].z3_variable
			prop_end = original_property.occurrences[happening][1].z3_variable
			all_capability_variables_with_numeric_influence = [cap.occurrences[happening].z3_variable for cap in all_capabilities_with_numeric_influence]
			caps_constraint = [Not(cap) for cap in all_capability_variables_with_numeric_influence]                
			constraint = Implies(And(*caps_constraint), prop_end == prop_start)
			constraints.append(constraint)

	return constraints



def has_effect_on_related_prop_in_same_cap(property: Property, capability: Capability):
	return False