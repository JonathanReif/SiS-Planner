from smt_planning.smt.StateHandler import StateHandler
from z3 import BoolRef
from typing import List

def create_property_dictionary_with_occurrences(happenings:int, event_bound:int) -> None:
	stateHandler = StateHandler()	
	property_dictionary = stateHandler.get_property_dictionary()
	property_dictionary.add_property_occurrences(happenings, event_bound)

def create_capability_dictionary_with_occurrences(happenings:int) -> None:
	capability_dictionary = StateHandler().get_capability_dictionary()
	capability_dictionary.add_capability_occurrences(happenings)
	
def create_resource_ids(happenings:int, event_bound:int) -> List[BoolRef]:
	resource_dictionary = StateHandler().get_resource_dictionary()
	resource_dictionary.add_resource_occurences(happenings, event_bound)

	resources_smt: List[BoolRef] = []
	for resource in resource_dictionary.resources.values(): 
		for inner_dict in resource.occurrences.values():
			for occurrence in inner_dict.values():
				resource_smt = occurrence.z3_variable == resource.id
				resources_smt.append(resource_smt) # type: ignore

	return resources_smt