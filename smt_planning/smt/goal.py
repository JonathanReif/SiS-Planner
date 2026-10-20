from z3 import Not

from smt_planning.smt.StateHandler import StateHandler
from smt_planning.smt.property_links import get_related_properties

def goal_smt(happenings: int):
	property_dictionary = StateHandler().get_property_dictionary()
	goals = []
	for goal_property_iri, goal_value_expressions in property_dictionary.goals.items():
		# Every goal may consist of multiple value expressions (e.g., goal > 5 , goal <= 10). Create assertions for every goal expression
		for goal_value_expression in goal_value_expressions:
			goal_property_z3_var = property_dictionary.get_required_property_occurrence(goal_property_iri).z3_variable					
			relation = goal_value_expression.logical_interpretation															
			value = goal_value_expression.value                                                            
			
			prop_type = property_dictionary.get_property_data_type(goal_property_iri) 
			if prop_type == "http://www.w3id.org/hsu-aut/DINEN61360#Real" or prop_type == "http://www.w3id.org/hsu-aut/DINEN61360#Integer":

				match relation:														    
					case "<":
						goal_smt = goal_property_z3_var < value # type: ignore
					case "<=":
						goal_smt = goal_property_z3_var <= value # type: ignore
					case "=":
						goal_smt = goal_property_z3_var == value
					case "!=":
						goal_smt = goal_property_z3_var != value
					case ">=":
						goal_smt = goal_property_z3_var >= value # type: ignore
					case ">":
						goal_smt = goal_property_z3_var > value # type: ignore
					case _:
						raise RuntimeError("Incorrent logical relation")
				goals.append(goal_smt)
			
			elif prop_type == "http://www.w3id.org/hsu-aut/DINEN61360#Boolean":
					match value: 
						case 'true':
							goal_smt = goal_property_z3_var
						case 'false':
							goal_smt = Not(goal_property_z3_var)
						case _:
							raise RuntimeError("Incorrect value for Boolean")
						
					goals.append(goal_smt)
		
		# 2: Relate goals. We need to get all outputs of the required capability and make sure that related output properties are bound to the valu of these outputs
		# Only constrain output properties because we are only interested in the final output. The input depends on the capability and must not be "over-constrained"
		# Handle related properties of every init property
		related_properties = get_related_properties(goal_property_iri)
		for related_property in related_properties:
			if (related_property.relation_type == "Input"): continue
			try:
				related_property_z3_var = property_dictionary.get_provided_property_occurrence(str(related_property.iri), happenings-1, 1).z3_variable
				relation_constraint = (related_property_z3_var == goal_property_z3_var)
				goals.append(relation_constraint)
			except KeyError: 
				print(f"While creating goals, there was no provided property with key {related_property.iri}.")

	return goals