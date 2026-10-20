from typing import Dict, Set, List
from z3 import Real, Bool, Int, AstRef
from enum import Enum
from smt_planning.types.Property import Property
from smt_planning.dicts.name_util import convert_z3_variable_to_iri
from smt_planning.types.PropertyOccurrence import PropertyOccurrence
from smt_planning.types.InstanceDescription import Precondition, Effect, Init, ResourceConfiguration, Goal, FreeVariable


class CapabilityType(Enum):
	ProvidedCapability = 1
	RequiredCapability = 2

class ExpressionGoal(Enum):
	Free_Variable = 0
	Requirement = 1
	Assurance = 2
	Actual_Value = 3

class PropertyDictionary:
	def __init__(self):
		self.provided_properties: Dict[str, Property] = {}
		self.required_properties: Dict[str, Property] = {}
		self.preconditions: Dict[str, Set[Precondition]] = {}
		self.effects: Dict[str, Set[Effect]] = {}
		self.inits: Dict[str, Set[Init]] = {}
		self.resource_configurations: Dict[str, Set[ResourceConfiguration]] = {}
		self.goals: Dict[str, Set[Goal]] = {}
		self.free_variables: Dict[str, Set[FreeVariable]] = {}

	def add_provided_property(self, iri: str, data_type: str, relation_type: str, capability_iris: Set[str], expression_goal: str = "", logical_interpretation: str = "", value: str = ""):
		property = Property(iri, data_type, relation_type, capability_iris)
		self.provided_properties.setdefault(iri, property)

	def add_property_occurrences(self, happenings: int, event_bound: int) -> None:
		for property in self.provided_properties.values():
			for happening in range(happenings):
				for event in range(event_bound):
					property_occurrence = PropertyOccurrence(property.iri, property.data_type, happening, event)
					property.add_occurrence(property_occurrence)

	def add_required_property_occurence(self, iri: str, data_type: str, relation_type: str, capability_iris: Set[str]) -> None:
		property = Property(iri, data_type, relation_type, capability_iris)
		self.required_properties.setdefault(iri, property)
		property_occurence = PropertyOccurrence(iri, data_type, 0, 0)
		self.required_properties[iri].add_occurrence(property_occurence)

	def get_required_property_occurrence(self, iri: str) -> PropertyOccurrence:
		if (not iri in self.required_properties):
			raise KeyError(f"There is no required property with key {iri}.")
		# Required props only have one entry, so return 0,0
		return self.required_properties[iri].occurrences[0][0]

	def get_provided_property_occurrence(self, iri: str, happening:int, event:int) -> PropertyOccurrence:
		if (not iri in self.provided_properties):
			raise KeyError(f"There is no provided property with key {iri} at happening {happening} and event {event}.")
		return self.provided_properties[iri].occurrences[happening][event]

	def get_property_occurence(self, iri: str, happening:int, event:int) -> PropertyOccurrence:
		try:
			property = self.get_required_property_occurrence(iri)
		except KeyError:
			try:
				property = self.get_provided_property_occurrence(iri, happening, event)
			except KeyError:
				raise KeyError(f"There is neither a provided nor a required property with key {str(iri)}.")
		return property
	

	def get_all_property_occurences(self) -> List[PropertyOccurrence]:
		'''
		Return all currently stored property occurrences
		'''
		all_properties = {**self.required_properties, **self.provided_properties}
		all_occurrences: List[PropertyOccurrence] = []
		for property in all_properties.values():
			occurrences = property.get_all_occurrences()
			all_occurrences.extend(occurrences)
		
		return all_occurrences


	def get_provided_property(self, iri:str) -> Property:
		if (not iri in self.provided_properties):
			raise KeyError(f"There is no provided property with key {iri}.")
		return self.provided_properties[iri]

	def get_property(self, iri:str) -> Property:
		all_properties = {**self.required_properties, **self.provided_properties}
		if (not iri in all_properties):
			raise KeyError(f"There is no property with key {iri}.")
		return all_properties[iri]

	def get_property_data_type(self, iri: str):
		property = self.get_property(iri)
		return property.data_type
	
	def get_property_relation_type(self, iri: str) -> str:
		property = self.get_property(iri)
		return property.relation_type
	
	def get_property_from_z3_variable(self, z3_variable: AstRef) -> PropertyOccurrence:
		all_properties = {**self.required_properties, **self.provided_properties}
		z3_var_components = convert_z3_variable_to_iri(str(z3_variable))
		prop = all_properties.get(z3_var_components.iri)
		if prop is None:
			raise KeyError(f"There is not a single property occurrence for the z3_variable {z3_variable}")

		property_occurrence = prop.occurrences[z3_var_components.happening][z3_var_components.event]
		return property_occurrence
	
	def add_instance_description(self, data_element_iri: str, cap_iri: str, cap_type: CapabilityType, expr_goal: str, logical_interpretation: str, value: str):
		# Every instance description with expression goal "Variable" is a free variable, whose value will be determined during planning.
		# As the value is determined by the planner, there must not be a value in the ontology.
		if expr_goal == "Variable":
			if value != "None":
				raise ValueError(f"The instance description of {data_element_iri} with the expression goal 'Variabe' has the value {value}. A Variable must not have a value.")
			instance = FreeVariable(data_element_iri, cap_iri, logical_interpretation)
			self.free_variables.setdefault(data_element_iri, set()).add(instance)
		
		# Every instance description with expression goal "Assurance" is an effect. It may or may not have a value (fixed effect vs. variable effects depending on formulas)
		elif expr_goal == "Assurance":
			instance = Effect(data_element_iri, cap_iri, logical_interpretation, value)
			self.effects.setdefault(data_element_iri, set()).add(instance)

		# Instance descriptions with expression goal "Requirement" can either be goals (requirements of the required cap) or preconditions of the provided cap
		elif expr_goal == "Requirement" and value != "None":
			if cap_type == CapabilityType.RequiredCapability:
				instance = Goal(data_element_iri, cap_iri, logical_interpretation, value)
				self.goals.setdefault(data_element_iri, set()).add(instance)
			else:
				instance = Precondition(data_element_iri, cap_iri, logical_interpretation, value)
				self.preconditions.setdefault(data_element_iri, set()).add(instance)
			
		# Instance descriptions with expression goal "Actual_Value" can either be inits (actual_values of the required cap) or resource configurations of the provided cap
		elif expr_goal == "Actual_Value" and value != "None":
			if cap_type == CapabilityType.RequiredCapability:
				instance = Init(data_element_iri, cap_iri, logical_interpretation, value)
				self.inits.setdefault(data_element_iri, set()).add(instance)
			else:
				instance = ResourceConfiguration(data_element_iri, cap_iri, logical_interpretation, value)
				self.resource_configurations.setdefault(data_element_iri, set()).add(instance)

		else:
			print(f"For the data element '{data_element_iri}' with the following instance information, no property was defined. Exp. Goal: {expr_goal}, Log. Int.: {logical_interpretation}, value: {value}")
			return
		
		self.get_property(data_element_iri).add_instance(instance)

	# TODO: This is pretty hacky to add inits afterwards. Should be better integrated into the architecture
	def add_init(self, data_element_iri: str, cap_iri: str, logical_interpretation: str, value: str):
		init = Init(data_element_iri, cap_iri, logical_interpretation, value)
		self.inits.setdefault(data_element_iri, set()).add(init)

	def prune_missing_capabilities(self, capability_dictionary) -> None:
		"""
		Remove properties and instance descriptions that reference pruned capabilities.
		After capability pruning, properties may still reference deleted capabilities.
		This method cleans up those dangling references.
		"""
		print("[PRUNING] Cleaning up PropertyDictionary after capability pruning...")

		# Get set of valid capability IRIs
		valid_capability_iris = set(capability_dictionary.provided_capabilities.keys())

		# Step 1: Remove provided properties that have no valid capabilities left
		provided_to_delete = []
		for prop_iri, prop in self.provided_properties.items():
			# Filter capability_iris: keep only valid ones
			prop.capability_iris = {cap_iri for cap_iri in prop.capability_iris if cap_iri in valid_capability_iris}

			# If property has no valid capabilities left, mark for deletion
			if len(prop.capability_iris) == 0:
				provided_to_delete.append(prop_iri)

		for prop_iri in provided_to_delete:
			del self.provided_properties[prop_iri]

		print(f"[PRUNING] Removed {len(provided_to_delete)} provided properties with no valid capabilities")

		# Step 2: Get set of all valid property IRIs (both provided and required)
		all_valid_property_iris = set(self.provided_properties.keys()) | set(self.required_properties.keys())

		# Step 3: Clean up ALL instance description collections
		# Keep only instance descriptions whose property IRI still exists
		instance_descriptions_removed = {
			'preconditions': 0,
			'effects': 0,
			'inits': 0,
			'resource_configurations': 0,
			'goals': 0,
			'free_variables': 0
		}

		for collection_name, collection in [
			('preconditions', self.preconditions),
			('effects', self.effects),
			('inits', self.inits),
			('resource_configurations', self.resource_configurations),
			('goals', self.goals),
			('free_variables', self.free_variables)
		]:
			props_to_delete = []
			for prop_iri, instance_set in collection.items():
				# Keep only if the property IRI still exists in either provided or required properties
				if prop_iri not in all_valid_property_iris:
					props_to_delete.append(prop_iri)
					instance_descriptions_removed[collection_name] += len(instance_set)

			for prop_iri in props_to_delete:
				del collection[prop_iri]

		print(f"[PRUNING] PropertyDictionary cleanup complete:")
		print(f"  - Properties remaining: {len(self.provided_properties)} provided, {len(self.required_properties)} required")
		print(f"  - Instance descriptions removed:")
		for name, count in instance_descriptions_removed.items():
			if count > 0:
				print(f"    - {name}: {count}")
