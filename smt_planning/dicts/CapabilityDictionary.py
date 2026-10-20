from typing import Dict, List, Set
from z3 import Bool, Int, AstRef
from smt_planning.dicts.PropertyDictionary import Property
from enum import Enum
from smt_planning.dicts.name_util import convert_iri_to_z3_variable, convert_z3_variable_to_iri

class PropertyChange(Enum):
	NoChange = 1
	ChangeByExpression = 2
	NumericConstant = 3
	SetTrue = 4
	SetFalse = 5

class CapabilityPropertyInfluence:
	def __init__(self, property: Property, effect: PropertyChange):
		self.property = property
		self.effect = effect

class CapabilityOccurrence:
	def __init__(self, iri: str, happening: int):
		self.iri = iri
		self.happening = happening
		self.event = 0	# Definition: All capability occurrences happen at event 0
		z3_variable_name = convert_iri_to_z3_variable(iri, happening, self.event)
		self.z3_variable = Bool(z3_variable_name)

'''
capabiltiy_type: The type of the capability, e.g., CaSk:ProvidedCapability (TODO do we need type?)
input_properties: The properties that are required for the capability to be executed
'''
class Capability:
	def __init__(self, iri: str, capability_type: str, input_properties: List[Property], output_properties: List[CapabilityPropertyInfluence]):
		self.iri = iri
		self.capability_type = capability_type
		self.input_properties = input_properties
		self.output_properties = output_properties
		self.occurrences: Dict[int, CapabilityOccurrence] = {}

	def add_occurrence(self, occurrence: CapabilityOccurrence):
		happening = occurrence.happening
		self.occurrences.setdefault(happening, occurrence)

	def add_input_property(self, property: Property):
		self.input_properties.append(property)

	def add_output_property(self, property_influence: CapabilityPropertyInfluence):
		self.output_properties.append(property_influence)

	def has_effect_on_property(self, property: Property) -> bool:
		# Get output of this property and see if it has an effect
		outputs = [influence for influence in self.output_properties if influence.property.iri == property.iri]
		if len(outputs) == 0: return False
		return (not outputs[0].effect == PropertyChange.NoChange)

	def sets_property_true(self, property: Property) -> bool:
		outputs = [influence for influence in self.output_properties if influence.property.iri == property.iri]
		if len(outputs) == 0: return False
		return (outputs[0].effect == PropertyChange.SetTrue)
	
	def sets_property_false(self, property: Property) -> bool:
		outputs = [influence for influence in self.output_properties if influence.property.iri == property.iri]
		if len(outputs) == 0: return False
		return (outputs[0].effect == PropertyChange.SetFalse)
	
	def get_occurrence_by_z3_variable(self, z3_variable_name: str) -> CapabilityOccurrence | None:
		# Filters occurrences for the given z3_variable. There should only be one result
		for occurrence in self.occurrences.values():
			if str(occurrence.z3_variable) == z3_variable_name:
				return occurrence
		
		return None
	
	def get_all_occurrences(self) -> List[CapabilityOccurrence]:
		# Double list comprehension to flatten the double dict-structure of self.occurrences
		occurrences = [occurrence for occurrence in self.occurrences.values()]
		return occurrences



class ConstraintInfo():
	def __init__(self, cap: str, constraintIri: str):
		self.cap = cap
		self.constraintIri = constraintIri

class CapabilityDictionary:
	def __init__(self):
		self.provided_capabilities: Dict[str, Capability] = {}
		self.required_capabilities: Dict[str, Capability] = {}
		self.input_capability_constraints: List[ConstraintInfo] = []
		self.output_capability_constraints: List[ConstraintInfo] = []

	def add_capability(self, iri: str, capability_type: str, input_properties: List[Property], output_properties: List[CapabilityPropertyInfluence]) -> None:
		if (capability_type == "http://www.w3id.org/hsu-aut/cask#ProvidedCapability"):
			self.add_provided_capability(iri, input_properties, output_properties)
		elif (capability_type == "http://www.w3id.org/hsu-aut/cask#RequiredCapability"):
			self.add_required_capability(iri, input_properties, output_properties) 

	def add_provided_capability(self, iri: str, input_properties: List[Property], output_properties: List[CapabilityPropertyInfluence]) -> None:
		capability = Capability(iri,"http://www.w3id.org/hsu-aut/cask#ProvidedCapability", input_properties, output_properties)
		self.provided_capabilities.setdefault(iri, capability)

	def add_required_capability(self, iri: str, input_properties: List[Property], output_properties: List[CapabilityPropertyInfluence]) -> None:
		capability = Capability(iri,"http://www.w3id.org/hsu-aut/cask#RequiredCapability", input_properties, output_properties)
		self.required_capabilities.setdefault(iri, capability)

	def add_capability_occurrences(self, happenings: int) -> None:
		capabilities = {**self.provided_capabilities, **self.required_capabilities}
		for capability in capabilities.values():
			for happening in range(happenings):
				capability_occurrence = CapabilityOccurrence(capability.iri, happening)
				capability.add_occurrence(capability_occurrence)

	def get_provided_capability(self, iri: str)-> Capability:
		if (not iri in self.provided_capabilities):
			raise KeyError(f"There is no provided capability with key {iri}.")
		return self.provided_capabilities[iri]

	def get_capability(self, iri:str) -> Capability:
		capabilities = {**self.provided_capabilities, **self.required_capabilities}
		if (not iri in capabilities):
			raise KeyError(f"There is no capability with key {iri}.")
		return capabilities[iri]

	def get_capability_occurrence(self, iri: str, happening:int) -> CapabilityOccurrence:
		capability = self.get_capability(iri)
		return capability.occurrences[happening]
	
	def get_all_capability_occurrences(self) -> List[CapabilityOccurrence]:	
		'''
		Return all currently stored capability occurrences
		'''
		all_capabilities = {**self.required_capabilities, **self.provided_capabilities}
		all_occurrences: List[CapabilityOccurrence] = []
		for capability in all_capabilities.values():
			occurrences = capability.get_all_occurrences()
			all_occurrences.extend(occurrences)
		
		return all_occurrences
	
	def get_capability_from_z3_variable(self, z3_variable: AstRef) -> CapabilityOccurrence:
		capabilities = {**self.provided_capabilities, **self.required_capabilities}
		z3_var_components = convert_z3_variable_to_iri(str(z3_variable))
		capability = capabilities.get(z3_var_components.iri)
		if capability is None:
			raise KeyError(f"There is no capability for the z3_variable {z3_variable}")

		capability_occurrence = capability.occurrences[z3_var_components.happening]
		return capability_occurrence

	def add_capability_constraint(self, cap: str, constraintIri: str, input: bool = False) -> None:
		if input:
			self.input_capability_constraints.append(ConstraintInfo(cap, constraintIri))
		else:
			self.output_capability_constraints.append(ConstraintInfo(cap, constraintIri))

	def prune_by_process(self, process_iri: str, query_handler):
		"""
		Remove capabilities that belong to simulations for OTHER processes.
		This is done AFTER all dictionaries are loaded to avoid dictionary sync issues.
		"""
		query = f"""
		PREFIX CSS: <http://www.w3id.org/hsu-aut/css#>
		PREFIX SiS: <http://www.semanticweb.org/reif/ontologies/SiS#>
		PREFIX VDI3633: <http://www.semanticweb.org/reif/ontologies/VDI3633#>
		SELECT ?cap WHERE {{
			?sim a VDI3633:Simulation ;
				 CSS:providesCapability ?cap ;
				 SiS:isSimulationFor ?proc .
			FILTER(?proc != <{process_iri}>)
		}}
		"""
		results = query_handler.query(query)
		caps_to_remove = [str(row['cap']) for row in results]

		for cap_iri in caps_to_remove:
			if cap_iri in self.provided_capabilities:
				del self.provided_capabilities[cap_iri]
				print(f"[PRUNING] Removed {cap_iri} as it belongs to another process")