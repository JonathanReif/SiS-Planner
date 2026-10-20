from typing import List
from z3 import Implies, Not

from smt_planning.smt.StateHandler import StateHandler

def getPropositionSupports(happenings: int, event_bound: int) -> List:
	'''
	Proposition support takes care of continuing property values. 
	It ensures that property values cannot randomly change from one happending to the next one.
	'''
	
	supports = []
	property_dictionary = StateHandler().get_property_dictionary()
	properties = property_dictionary.provided_properties.values()

	for happening in range(happenings)[1:]:
		for property in properties:
			if property.data_type == "http://www.w3id.org/hsu-aut/DINEN61360#Boolean":
				property_current_happening_start = property.occurrences[happening][0].z3_variable
				property_last_happening_end = property.occurrences[happening-1][event_bound-1].z3_variable

				# Track change between happenings, so that no random change is possible
				# TODO: Why do we need both implies (positive and negative)? Isn't this the same as setting start and last_end equal?
				# 1: If a property is set at start of a happening, it must have been set at the last happening's end 
				support = Implies(property_current_happening_start, property_last_happening_end)
				supports.append(support)
				
				# 1: If a property is NOT set at start of a happening, it must NOT have been set at the last happening's end 
				support_negated = Implies(Not(property_current_happening_start), Not(property_last_happening_end))
				supports.append(support_negated)

	return supports
