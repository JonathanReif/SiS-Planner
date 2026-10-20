from typing import List
from z3 import Implies, Not, BoolRef, ArithRef

from smt_planning.smt.StateHandler import StateHandler
from smt_planning.smt.property_links import get_related_properties

def capability_effects_smt(happenings: int, event_bound: int) -> List[BoolRef]:
	property_dictionary = StateHandler().get_property_dictionary()
	capability_dictionary = StateHandler().get_capability_dictionary()
	effects_smt = []
	for happening in range(happenings):
		for property_iri, effect_list in property_dictionary.effects.items():
			for effect in effect_list:
				#property_iri = effect.iri
				value = effect.value
				current_capability = capability_dictionary.get_capability_occurrence(effect.cap_iri, happening).z3_variable
				effect_property = property_dictionary.get_provided_property_occurrence(property_iri, happening, 1).z3_variable
				# Case 1: Constant effect 																					
				if value != "None": 																								
					prop_type = property_dictionary.get_property_data_type(property_iri) 												
					effect_smt = generate_effect_constraint(current_capability, effect_property, prop_type, effect.logical_interpretation, value)	
					effects_smt.append(effect_smt)
				else: 
					# Case 2: Dynamic, formula effect
					# TODO: Formula effects are currently handled in capability_constraints. Would be better in effects.py, but we need the data we have here...
					pass
				related_properties = get_related_properties(property_iri)
				for related_property in related_properties:
					property = property_dictionary.get_property_occurence(related_property.iri, happening, 1)
					effect_smt = Implies(current_capability, effect_property == property.z3_variable)
					effects_smt.append(effect_smt)
				
	return effects_smt

def generate_effect_constraint(capability: BoolRef, property: BoolRef | ArithRef, prop_type: str, relation: str, value: str) -> BoolRef | None:	
	
	if prop_type == "http://www.w3id.org/hsu-aut/DINEN61360#Real" or prop_type == "http://www.w3id.org/hsu-aut/DINEN61360#Integer":
		match relation:
			case "<":
				effect_smt = Implies(capability, property < value)									 # type: ignore
			case "<=":
				effect_smt = Implies(capability, property <= value)									# type: ignore
			case "=":
				effect_smt = Implies(capability, property == value)									
			case "!=":
				effect_smt = Implies(capability, property != value)									
			case ">=":
				effect_smt = Implies(capability, property >= value)									# type: ignore
			case ">":
				effect_smt = Implies(capability, property > value)									# type: ignore
			case _:
				raise RuntimeError("Incorrect logical relation")
		return effect_smt
	
	elif prop_type == "http://www.w3id.org/hsu-aut/DINEN61360#Boolean":
		match value: 
			case 'true':
				effect_smt = Implies(capability, property)
			case 'false':
				effect_smt = Implies(capability, Not(property))
			case _:
				raise RuntimeError("Incorrect value for Boolean")
		return effect_smt