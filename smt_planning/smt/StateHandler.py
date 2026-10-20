from rdflib import Graph

from smt_planning.dicts.CapabilityDictionary import CapabilityDictionary
from smt_planning.dicts.PropertyDictionary import PropertyDictionary
from smt_planning.dicts.ResourceDictionary import ResourceDictionary
from smt_planning.ontology_handling.query_handlers import QueryHandler

# Singleton class
class StateHandler:
	
	_instance = None

	def __new__(cls):
		if cls._instance is None:
			cls._instance = super(StateHandler, cls).__new__(cls)
			cls.__graph = None
			cls.__property_dictionary = None
			cls.__capability_dictionary = None
			cls.__resource_dictionary = None
			cls.__process_iri = None
		return cls._instance

	def set_graph(self, graph: Graph) -> None:
		self.__graph = graph
	
	def get_graph(self) -> Graph:
		assert self.__graph is not None
		return self.__graph
	
	def set_query_handler(self, query_handler: QueryHandler) -> None:
		self.query_handler = query_handler

	def get_query_handler(self) -> QueryHandler:
		return self.query_handler

	def set_property_dictionary(self, property_dictionary: PropertyDictionary):
		self.__property_dictionary = property_dictionary
	
	def get_property_dictionary(self) -> PropertyDictionary:
		assert self.__property_dictionary is not None
		return self.__property_dictionary
	
	def set_capability_dictionary(self, capability_dictionary: CapabilityDictionary):
		self.__capability_dictionary = capability_dictionary
	
	def get_capability_dictionary(self) -> CapabilityDictionary:
		assert self.__capability_dictionary is not None
		return self.__capability_dictionary
	
	def set_resource_dictionary(self, resource_dictionary: ResourceDictionary):
		self.__resource_dictionary = resource_dictionary

	def get_resource_dictionary(self) -> ResourceDictionary:
		assert self.__resource_dictionary is not None
		return self.__resource_dictionary

	def set_process_iri(self, process_iri: str) -> None:
		self.__process_iri = process_iri

	def get_process_iri(self) -> str:
		return self.__process_iri

	def reset_caches(self) -> None:
		"""Reset all cached dictionaries to free memory between planning requests"""
		self.__graph = None
		self.__property_dictionary = None
		self.__capability_dictionary = None
		self.__resource_dictionary = None
		self.__process_iri = None
		# NOTE: Do NOT reset query_handler here - it's needed during the request!

	@classmethod
	def reset_singleton(cls) -> None:
		"""Completely reset the singleton instance to free all memory"""
		cls._instance = None
