from smt_planning.smt.StateHandler import StateHandler
from smt_planning.smt.property_links import get_related_properties
from z3 import BoolSort, IntSort, RealSort, Bool

def bind_floating_variables():
	# All the related props of output values at 0_0 need to be bound. Otherwise if they are floating, the goal at happening_1 value can be taken for 0_0. 
	# This in turn leads to no capabilities getting invoked
	property_dictionary = StateHandler().get_property_dictionary()
	goal_binding_assertions = []
	for goal in property_dictionary.goals:
		# add all goals themselves as we need to look into them as well.
		properties_related_to_goal = get_related_properties(goal)
		
		# If a single one of the properties related to goal is bound as an init, we can skip it. Else, bind
		if any(prop.iri in property_dictionary.inits.keys() for prop in properties_related_to_goal): continue
		
		for goal_related_prop in properties_related_to_goal:
			var = property_dictionary.get_property_occurence(goal_related_prop.iri, 0, 0).z3_variable
			
			if str(var.sort()) == str(BoolSort()): 
				goal_binding_assertion = var == False
			elif str(var.sort()) == str(IntSort()): 
				goal_binding_assertion = var == 0
			elif str(var.sort()) == str(RealSort()): 
				goal_binding_assertion = var == 0
			else: 
				print(f'The type {var.sort()} is not yet supported')

			goal_binding_assertions.append(goal_binding_assertion)

	return goal_binding_assertions