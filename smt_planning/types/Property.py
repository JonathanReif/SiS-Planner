from typing import Set, Dict, List

from smt_planning.types.PropertyOccurrence import PropertyOccurrence
from smt_planning.types.InstanceDescription import InstanceDescription


'''
iri is the IRI of the data element
data_type is some instance of http://www.w3id.org/hsu-aut/DINEN61360#Simple_Data_Type
relation_type is the relation type of the property, i.e., "hasInput" or "hasOutput"
'''
class Property:
	def __init__(self, iri: str, data_type: str, relation_type: str, capability_iris: Set[str]):
		self.iri = iri
		self.data_type = data_type
		self.relation_type = relation_type
		self.capability_iris = capability_iris
		self.occurrences: Dict[int, Dict[int, PropertyOccurrence]] = {}
		self.instances: List[InstanceDescription] = []

	def add_occurrence(self, occurrence: PropertyOccurrence):
		happening = occurrence.happening
		event = occurrence.event
		self.occurrences.setdefault(happening, {}).setdefault(event, occurrence)

	def get_all_occurrences(self) -> List[PropertyOccurrence]:
		# Double list comprehension to flatten the double dict-structure of self.occurrences
		occurrences = [value for inner_dict in self.occurrences.values() for value in inner_dict.values()]
		return occurrences

	def get_occurrence_by_z3_variable(self, z3_variable_name: str) -> PropertyOccurrence | None:
		# Filters occurrences for the given z3_variable. There should only be one result
		happening_occurrences = [occ for occ in self.occurrences.values()]
		all_occurrences_2d = [list(occ.values()) for occ in happening_occurrences]
		all_occurrences: List[PropertyOccurrence] = []
		[all_occurrences.extend(occ) for occ in all_occurrences_2d]
		try:
			occurrence = [occurrence for occurrence in all_occurrences if str(occurrence.z3_variable) == z3_variable_name][0]
			return occurrence
		except:
			return None
		
	def add_instance(self, instance: InstanceDescription):
		self.instances.append(instance)
	

	def __lt__(self, other):
		return self.iri < other.iri  # Comparison / Sorting by IRI string 

	def __repr__(self):
		return f"Property(iri={self.iri})"
    
	def __eq__(self, other):
		return self.iri == other.iri
    
	def __hash__(self):
		return hash(self.iri)
