from typing import TypedDict
from rdflib import Graph, URIRef, Literal, Variable
from rdflib.query import Result
from rdflib.namespace import OWL
from urllib.parse import urlparse
from pathlib import Path
import json
import requests
from abc import ABC, abstractmethod

class QueryHandler(ABC):

	@abstractmethod
	def query(self, query_string: str) -> Result:
		pass

class FileQueryHandler(QueryHandler):
	def __init__(self, filename: str) -> None:
		# Create a Graph
		from smt_planning.smt.StateHandler import StateHandler
		state_handler = StateHandler()
		graph = Graph()
		state_handler.set_graph(graph)

		self._parsed = set()
		self._parse_file(graph, filename)
	
	def _parse_file(self, graph: Graph, location: str) -> None:
		"""Parse a file/IRI into ``graph`` and follow imports."""

		if location in self._parsed:
				return
		self._parsed.add(location)

		graph.parse(location)

		base = Path(location).parent
		for imported in set(graph.objects(None, OWL.imports)):
				iri = str(imported)
				if urlparse(iri).scheme == "":
					iri = str((base / iri).resolve())
				self._parse_file(graph, iri)

	def query(self, query_string: str) -> Result:
		from smt_planning.smt.StateHandler import StateHandler
		graph = StateHandler().get_graph()
		results = graph.query(query_string)
		return results
	


class SparqlEndpointQueryHandler(QueryHandler):
	def __init__(self, endpoint_url) -> None:
		self.endpoint_url = endpoint_url
		# Define the headers
		self.headers = {
			"Accept": "application/sparql-results+json",  # or "application/sparql-results+xml" for XML format
			"Content-Type": "application/sparql-query",
		}
		self.params = {
			"infer": "false"
		}
	

	def query(self, query_string: str) -> Result:

		# Send the request
		response = requests.post(self.endpoint_url, data=query_string, headers=self.headers, params=self.params)

		# Check if the request was successful
		if response.status_code == 200:
			# Process the results and transform bindings to be compliant with rdflib Result
			data = json.loads(response.text)
			bindings = data['results']['bindings']
			labels = [Variable(label) for label in data['head']['vars']]  # Creating Variable instances for each label
			rows = []
			for b in bindings:
				row = {}
				for label in labels:
					label_str = str(label)
					if label_str in b:
						# Creating URIRef or Literal based on the type
						value = URIRef(b[label_str]['value']) if b[label_str]['type'] == 'uri' else Literal(b[label_str]['value'])
						row[label] = value
					else:
						# row[label] = None
						continue
				rows.append(row)

			# Creating an rdflib Result object
			result = Result('SELECT')
			result.vars = labels  # The variables selected in the SPARQL query
			result.bindings = rows  # The rows of results

			return result
		else:
			# print("Query failed. Status code:", response.status_code)
			raise Exception("Query failed. Status code:", response.status_code)


class ResultElement(TypedDict):
    value: str | int | bool
    type: str

class EndpointQueryResult:
	def __init__(self, iri: str, resElement: ResultElement) -> None:
		self.iri = iri
		self.value = resElement["value"]
		self.type = resElement["type"]
		pass

	def __eq__(self, other) -> bool:
		if isinstance(other, EndpointQueryResult):
			return ((self.value == other.value))
		else:
			return False
		
	def __hash__(self) -> int:
		return hash(self.iri)
	
	def __str__(self) -> str:
		return str(self.value)

