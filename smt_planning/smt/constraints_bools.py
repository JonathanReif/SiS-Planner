from z3 import Implies, Not, Or
from typing import List

from smt_planning.smt.StateHandler import StateHandler
from smt_planning.dicts.CapabilityDictionary import Capability
from smt_planning.smt.property_links import get_related_properties
from smt_planning.smt.capability_links import get_related_capabilities

def get_bool_constraints(happenings: int, event_bound: int) -> List:

	stateHandler = StateHandler()	
	property_dictionary = stateHandler.get_property_dictionary()
	capability_dictionary = stateHandler.get_capability_dictionary()
	
	constraints = []
	properties = property_dictionary.provided_properties.values()
	for original_property in properties:
		if original_property.data_type != "http://www.w3id.org/hsu-aut/DINEN61360#Boolean": continue

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

		all_true_setting_capabilities: List[Capability] = []
		all_false_setting_capabilities: List[Capability] = []
		for capability in all_capabilities:
			for property in all_properties:
				if capability.sets_property_true(property):
					all_true_setting_capabilities.append(capability)
				if capability.sets_property_false(property):
					all_false_setting_capabilities.append(capability)

		for happening in range(happenings):
			prop_start = original_property.occurrences[happening][0].z3_variable
			prop_end = original_property.occurrences[happening][1].z3_variable
			all_true_setting_capability_variables = [cap.occurrences[happening].z3_variable for cap in all_true_setting_capabilities]
			all_false_setting_capability_variables = [cap.occurrences[happening].z3_variable for cap in all_false_setting_capabilities]
			positive_constraint = Implies(prop_end, Or(prop_start, *all_true_setting_capability_variables))
			negative_constraint = Implies(Not(prop_end), Or(Not(prop_start), *all_false_setting_capability_variables))

			constraints.append(positive_constraint)
			constraints.append(negative_constraint)

	return constraints