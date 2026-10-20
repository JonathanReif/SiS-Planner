from typing import List

from smt_planning.smt.StateHandler import StateHandler

def get_capability_constraints():
	# Get all capability constraint IRIs and check whether its a constraint on an input or output
	# GROUP_CONCAT is used as we're only interested in the constraints and not the individual arguments as separate entries
	# //TODO: The BIND() clauses have to be used for rdflib as it otherwise fails with the error "variable unbound". It cannot handle GROUP_CONCAT for unbound variables. 
	# It would be better to replace this with a Python snippet concatenating the arguments because this query is unreadable
	query_string = """
	PREFIX OM: <http://openmath.org/vocab/math#>
	PREFIX CSS: <http://www.w3id.org/hsu-aut/css#>
	PREFIX VDI3682: <http://www.w3id.org/hsu-aut/VDI3682#>
	SELECT ?cap ?constraint
		(GROUP_CONCAT(DISTINCT ?inputArgument; SEPARATOR=",") AS ?inputArguments) 
		(GROUP_CONCAT(DISTINCT ?outputArgument; SEPARATOR=",") AS ?outputArguments)
	WHERE {
		?cap ^CSS:requiresCapability ?process;
			CSS:isRestrictedBy ?constraint.

		# Look for recursively nested arguments on any layer of an equation connected with an input
		OPTIONAL {
			?constraint (OM:arguments/rdf:rest*/rdf:first)* ?maybeInput.
			?process VDI3682:hasInput/VDI3682:isCharacterizedBy ?maybeInput.
		}	
		BIND(
			IF(BOUND(?maybeInput), STR(?maybeInput), "") 
			AS ?inputArgument
		)

		# Look for recursively nested arguments on any layer of an equation connected with an output
		OPTIONAL {
			?constraint (OM:arguments/rdf:rest*/rdf:first)* ?maybeOutput.
			?process VDI3682:hasOutput/VDI3682:isCharacterizedBy ?maybeOutput.
		}
		BIND(
			IF(BOUND(?maybeOutput), STR(?maybeOutput), "") 
			AS ?outputArgument
		)
	}
	GROUP BY ?cap ?constraint
	"""
	
	stateHandler = StateHandler()
	capability_dictionary = stateHandler.get_capability_dictionary()
	query_handler = stateHandler.get_query_handler()
	results = query_handler.query(query_string)
	
	for row in results:
		# As soon as an outputArgument is present, the constraint is considered an output constraint
		if row['outputArguments']:																
			capability_dictionary.add_capability_constraint(str(row['cap']), str(row['constraint']))
		# If a row only has an inputArgument, the constraint is considered an input constraint
		if (row['inputArguments'] and not row['outputArguments']):									 
			capability_dictionary.add_capability_constraint(str(row['cap']), str(row['constraint']), True)