from typing import List
from z3 import BoolRef, ArithRef
from smt_planning.dicts.PropertyDictionary import PropertyDictionary, Property
from smt_planning.dicts.CapabilityDictionary import CapabilityDictionary

def fix_constants(property_dictionary: PropertyDictionary, capability_dictionary: CapabilityDictionary, happenings: int, event_bound: int):
	# TODO: Add a real logic to find constants. For now hard coded. Rule for constants: properties that are not written by caps
	constants : List[Property]  = [prop for prop in property_dictionary.provided_properties.values() if "Module_StationID" in prop.iri]
	constant_expressions : List[BoolRef | ArithRef | bool] = []
	for constant in constants:
		occurences_vars = [prop.z3_variable for prop in constant.get_all_occurrences()]
		constant_constraint = [occurences_vars[i] == occurences_vars[i+1] for i in range(len(occurences_vars) - 1)]
		constant_expressions.extend(constant_constraint)

	return constant_expressions
		