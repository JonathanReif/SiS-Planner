from z3 import Not, Or
import itertools
from typing import Set, Tuple
from smt_planning.smt.StateHandler import StateHandler
from smt_planning.dicts.PropertyDictionary import Property
from smt_planning.dicts.CapabilityDictionary import CapabilityPropertyInfluence
from smt_planning.smt.property_links import get_related_properties

def get_capability_mutexes(happenings: int):

	resource_dictionary = StateHandler().get_resource_dictionary()

	constraints = []

	# Assumption: Make all caps of one resource mutex, i.e. multiple caps of one resource cannot be used at a time
	for res in resource_dictionary.resources.values(): 
		combinations = list(itertools.combinations(res.capabilities, 2))

		for happening in range(happenings):
			for combination in combinations:
				constraint = Or(Not(combination[0].occurrences[happening].z3_variable), Not(combination[1].occurrences[happening].z3_variable))
				constraints.append(constraint)
				
	
	capability_mutex_tuples: Set[Tuple[str, str]] = set()
	property_dictionary = StateHandler().get_property_dictionary()
	capability_dictionary = StateHandler().get_capability_dictionary()

	# For every provided prop, get related props. Then get all the caps and make them mutex.
	# Reasoning: A cap changing a property and another one changing a related one must me mutex
	provided_props = property_dictionary.provided_properties.values()
	for prop in provided_props:
		related_props = get_related_properties(prop.iri)
		prop_and_related = [prop, *related_props]
		capabilities: Set[str] = set.union(*[p.capability_iris for p in prop_and_related])
		current_prop_capability_mutex_tuples = set(itertools.combinations(capabilities, 2))
		capability_mutex_tuples.update(current_prop_capability_mutex_tuples)
	
	for cap_tuple in capability_mutex_tuples:
		for happening in range(happenings):
			cap_a = capability_dictionary.get_capability_occurrence(cap_tuple[0], happening)
			cap_b = capability_dictionary.get_capability_occurrence(cap_tuple[1], happening)
			constraint = Or(Not(cap_a.z3_variable), Not(cap_b.z3_variable))
			constraints.append(constraint)

	return constraints



class CapabilityTuple:
	def __init__(self, capability_a: str, capability_b: str):
		self.capability_a = capability_a
		self.capability_b = capability_b

	def __eq__(self, other):
		if isinstance(other, CapabilityTuple):
			return {self.capability_a, self.capability_b} == {other.capability_a, other.capability_b}
		return False

	def __hash__(self):
		# Use frozenset to create a hash independent of order
		return hash(frozenset([self.capability_a, self.capability_b]))