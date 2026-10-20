from z3 import Not

from smt_planning.smt.StateHandler import StateHandler
from smt_planning.smt.property_links import get_related_properties

def init_smt():
	'''
	Creates SMT expressions for inits and resource configurations (both are handled similarily)
	'''
	property_dictionary = StateHandler().get_property_dictionary()
	init_constraints = []
	inits = property_dictionary.inits.items()
	resource_configs = property_dictionary.resource_configurations.items()
	inits_and_configs = dict(inits) | dict(resource_configs)
	for property_iri, value_expression in inits_and_configs.items():

		# Every init may consist of multiple value expressions (e.g., init > 5 , init <= 10). Create assertions for every init expression
		for init_expression in value_expression:
			init_property_z3_var = property_dictionary.get_property_occurence(property_iri, 0, 0).z3_variable
			relation = init_expression.logical_interpretation															
			value = init_expression.value														    
		
			prop_type = property_dictionary.get_property_data_type(property_iri) 
			if prop_type == "http://www.w3id.org/hsu-aut/DINEN61360#Real" or prop_type == "http://www.w3id.org/hsu-aut/DINEN61360#Integer":

				match relation:
					case "<":
						init_smt = init_property_z3_var < value # type: ignore
					case "<=":
						init_smt = init_property_z3_var <= value # type: ignore
					case "=":
						init_smt = init_property_z3_var == value 
					case "!=":
						init_smt = init_property_z3_var != value 
					case ">=":
						init_smt = init_property_z3_var >= value # type: ignore
					case ">":
						init_smt = init_property_z3_var > value # type: ignore
					case _:
						raise RuntimeError("Incorrent logical relation")
				init_constraints.append(init_smt)

			elif prop_type == "http://www.w3id.org/hsu-aut/DINEN61360#Boolean":
				match value: 
					case 'true':
						init_smt = init_property_z3_var
					case 'false':
						init_smt = Not(init_property_z3_var)
					case _:
						raise RuntimeError("Incorrect value for Boolean")
					
				init_constraints.append(init_smt)
	
	return init_constraints