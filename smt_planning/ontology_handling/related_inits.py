from typing import List

from smt_planning.smt.StateHandler import StateHandler
from smt_planning.smt.property_links import get_related_properties
from smt_planning.types.Property import Property
from smt_planning.types.InstanceDescription import Init

def find_all_related_inits():
	'''
	Makes sure that all related properties are also added to the inits entry
	'''
	property_dictionary = StateHandler().get_property_dictionary()
	
	init_items = list(property_dictionary.inits.items())
	for init_property_iri, init_value_expressions in init_items:
		related_properties = get_related_properties(init_property_iri)
		for init_expression in init_value_expressions:
			add_related_init(related_properties, init_expression)


def add_related_init(related_properties: List[Property], init_expression: Init):
	property_dictionary = StateHandler().get_property_dictionary()
	
	for related_property in related_properties:
			for cap_iri in related_property.capability_iris:
				property_dictionary.add_init(related_property.iri, cap_iri, init_expression.logical_interpretation, init_expression.value)