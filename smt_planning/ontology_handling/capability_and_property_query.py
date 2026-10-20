import itertools
from typing import List, Tuple

from smt_planning.smt.StateHandler import StateHandler
from smt_planning.dicts.PropertyDictionary import PropertyDictionary, CapabilityType
from smt_planning.dicts.CapabilityDictionary import CapabilityDictionary, CapabilityPropertyInfluence, PropertyChange
from smt_planning.dicts.ResourceDictionary import ResourceDictionary

def get_all_properties(required_cap_iri: str) -> PropertyDictionary:
	
	# We need to get properties that belong to the capabilitiy inputs / outputs themselves as well as to resources. Important: Since rdflib has issues with UNION queries, we need to do two separate queries and combine the results afterwards.
	# 
	query_string_1 = """
	PREFIX DINEN61360: <http://www.w3id.org/hsu-aut/DINEN61360#>
	PREFIX CSS: <http://www.w3id.org/hsu-aut/css#>
	PREFIX CaSk: <http://www.w3id.org/hsu-aut/cask#>
	PREFIX VDI3682: <http://www.w3id.org/hsu-aut/VDI3682#>
	PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
	SELECT ?de (GROUP_CONCAT(?cap; SEPARATOR=",") AS ?caps) ?capType ?dataType ?relationType ?expr_goal ?log ?val WHERE {
		# this part gets all the data elements of resources (that must provide a cap)
		?resource CSS:providesCapability ?cap.
		BIND(CaSk:ProvidedCapability as ?capType).
		?resource DINEN61360:has_Data_Element ?de.
		# Filter out results from the other union set to not get strange duplicates
		FILTER(
		NOT EXISTS {
			?inout a/rdfs:subClassOf VDI3682:State.
			?inout VDI3682:isCharacterizedBy ?id.
		})
		
		?inout VDI3682:isCharacterizedBy ?id.
		# All caps must have a type, that can either be provided or required (but if required, filter for the one we're plannning for)
		VALUES ?relation {
			VDI3682:hasInput VDI3682:hasOutput
		}.
		BIND(STRAFTER(STR(?relation), "has") AS ?relationType)
		VALUES ?capType {
			CaSk:ProvidedCapability CaSk:RequiredCapability 
		}.
		# Filter to get only provided caps AND the one required that we are planning for
		?de DINEN61360:has_Instance_Description ?id.
		# All DE need ID with datatype, exp goal (optional), log (optional), value (optional)
		?id a ?dataType.
		?dataType rdfs:subClassOf DINEN61360:Simple_Data_Type.
		FILTER(?dataType != DINEN61360:Simple_Data_Type) # Only get the real subclasses, not Simple_D_T itself
		OPTIONAL {
			?id DINEN61360:Expression_Goal ?expr_goal.
		}
		OPTIONAL {
			?id DINEN61360:Logic_Interpretation ?log .
		}
		OPTIONAL {
			?id DINEN61360:Value ?val.
		}  
	} GROUP BY ?de ?capType ?dataType ?relationType ?expr_goal ?log ?val
	"""

	query_string_2 = """
	PREFIX DINEN61360: <http://www.w3id.org/hsu-aut/DINEN61360#>
	PREFIX CSS: <http://www.w3id.org/hsu-aut/css#>
	PREFIX CaSk: <http://www.w3id.org/hsu-aut/cask#>
	PREFIX VDI3682: <http://www.w3id.org/hsu-aut/VDI3682#>
	PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
	SELECT ?de (GROUP_CONCAT(?cap; SEPARATOR=",") AS ?caps) ?capType ?dataType ?relationType ?expr_goal ?log ?val WHERE {
		# this part gets all properties that are directly connected to a process / capability
			?cap a ?capType;
				^CSS:requiresCapability ?process.
				?process ?relation ?inout.
			FILTER(?capType = CaSk:ProvidedCapability || ?cap = <{required_cap_iri}>)
		
		?inout VDI3682:isCharacterizedBy ?id.
		# All caps must have a type, that can either be provided or required (but if required, filter for the one we're plannning for)
		VALUES ?relation {
			VDI3682:hasInput VDI3682:hasOutput
		}.
		BIND(STRAFTER(STR(?relation), "has") AS ?relationType)
		VALUES ?capType {
			CaSk:ProvidedCapability CaSk:RequiredCapability 
		}.
		# Filter to get only provided caps AND the one required that we are planning for
		?de DINEN61360:has_Instance_Description ?id.
		# All DE need ID with datatype, exp goal (optional), log (optional), value (optional)
		?id a ?dataType.
		?dataType rdfs:subClassOf DINEN61360:Simple_Data_Type.
		FILTER(?dataType != DINEN61360:Simple_Data_Type) # Only get the real subclasses, not Simple_D_T itself
		OPTIONAL {
			?id DINEN61360:Expression_Goal ?expr_goal.
		}
		OPTIONAL {
			?id DINEN61360:Logic_Interpretation ?log .
		}
		OPTIONAL {
			?id DINEN61360:Value ?val.
		}  
	} GROUP BY ?de ?capType ?dataType ?relationType ?expr_goal ?log ?val
	"""
	query_string_2 = query_string_2.replace('{required_cap_iri}', required_cap_iri)
	query_handler = StateHandler().get_query_handler()
	results_1 = query_handler.query(query_string_1)
	results_2 = query_handler.query(query_string_2)

	properties = PropertyDictionary()
	
	# Combine results from both queries into a single iterator
	for row in itertools.chain(results_1, results_2):
		caps = set(row['caps'].split(","))
		
		if str(row['capType']) == "http://www.w3id.org/hsu-aut/cask#RequiredCapability":
			# directly with occurrence because properties of required capabilities only have one occurrence
			properties.add_required_property_occurence(str(row['de']), str(row['dataType']), str(row['relationType']), caps)  
			for cap in caps: 
				properties.add_instance_description(str(row['de']), cap, CapabilityType.RequiredCapability, str(row['expr_goal']), str(row['log']), str(row['val']))
		else:
			properties.add_provided_property(str(row['de']), str(row['dataType']), str(row['relationType']), caps)  
			for cap in caps: 
				properties.add_instance_description(str(row['de']), cap, CapabilityType.ProvidedCapability, str(row['expr_goal']), str(row['log']), str(row['val'])) 
	
	return properties

def get_provided_capabilities(required_cap_iri: str) -> Tuple[CapabilityDictionary, ResourceDictionary]:
	query_string = """
	PREFIX DINEN61360: <http://www.w3id.org/hsu-aut/DINEN61360#>
	PREFIX CSS: <http://www.w3id.org/hsu-aut/css#>
	PREFIX CaSk: <http://www.w3id.org/hsu-aut/cask#>
	PREFIX VDI3682: <http://www.w3id.org/hsu-aut/VDI3682#>
	PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
	SELECT DISTINCT ?cap ?de ?res ?capType WHERE {
		?cap a ?capType;
			^CSS:requiresCapability ?process.
		?capType rdfs:subClassOf CSS:Capability.
		FILTER(?capType = CaSk:ProvidedCapability || ?cap = <{required_cap_iri}>)
		?process VDI3682:hasInput ?input.
		?input VDI3682:isCharacterizedBy ?id.
		?de DINEN61360:has_Instance_Description ?id.
		OPTIONAL{
			?res CSS:providesCapability ?cap.
		}
	}
	"""
	query_string = query_string.replace('{required_cap_iri}', required_cap_iri)
	query_handler = StateHandler().get_query_handler()
	results = query_handler.query(query_string)
	
	property_dictionary = StateHandler().get_property_dictionary()
	capability_dictionary = CapabilityDictionary()

	caps = set([str(row['cap']) for row in results])
	for cap in caps:
		# Input properties can be retrieved from query
		inputs = [str(row['de']) for row in results if (str(row['cap']) == cap)]
		input_properties = [property_dictionary.get_property(input) for input in inputs]
		# Outputs need to have their effect attached and are more tricky
		outputs = get_output_influences_of_capability(cap)
		capType = [str(row['capType']) for row in results if (str(row['cap']) == cap)][0]
		capability_dictionary.add_capability(cap, capType, input_properties, outputs)

	resource_dictionary = ResourceDictionary()

	resources = set([str(row['res']) for row in results if row['res'] is not None])
	for resource in resources:
		caps = set([str(row['cap']) for row in results if (str(row['res']) == resource)])
		resource_caps = [capability_dictionary.get_provided_capability(cap) for cap in caps]
		resource_dictionary.add_resource(resource, resource_caps)

	return capability_dictionary, resource_dictionary

# TODO one query for both ... 
def get_output_influences_of_capability(capability_iri: str) -> List[CapabilityPropertyInfluence] :
	query_string = """
	PREFIX DINEN61360: <http://www.w3id.org/hsu-aut/DINEN61360#>
	PREFIX CSS: <http://www.w3id.org/hsu-aut/css#>
	PREFIX CaSk: <http://www.w3id.org/hsu-aut/cask#>
	PREFIX VDI3682: <http://www.w3id.org/hsu-aut/VDI3682#>
	PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
	PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
	PREFIX OM: <http://openmath.org/vocab/math#>
	PREFIX OM-Relation1: <http://www.openmath.org/cd/relation1#>
	SELECT ?cap ?input_de ?inputClass ?inputExpressionGoal ?inputValue ?output_de ?outputClass ?outputValue 
	?equalConstraint ?inputStateSubclass ?outputStateSubclass WHERE {
		BIND(<{capability_iri}> AS ?cap)
		?cap a CaSk:ProvidedCapability;
			^CSS:requiresCapability ?process.
		?process VDI3682:hasInput ?input.
		?input a ?inputClass.
		?inputClass rdfs:subClassOf* ?inputStateSubclass.
		?inputStateSubclass rdfs:subClassOf VDI3682:State.
		?input VDI3682:isCharacterizedBy ?input_id.
		?input_de DINEN61360:has_Instance_Description ?input_id;
				DINEN61360:has_Type_Description ?td.
		?input_id a ?dataType.
		?dataType rdfs:subClassOf DINEN61360:Simple_Data_Type.
		OPTIONAL {
			?input_id DINEN61360:Expression_Goal ?inputExpressionGoal.
		}
		OPTIONAL {
			?input_id DINEN61360:Value ?inputValue.
		}
		?process VDI3682:hasOutput ?output.
		?output a ?outputClass.
		?outputClass rdfs:subClassOf* ?outputStateSubclass.
		?outputStateSubclass rdfs:subClassOf VDI3682:State.
		?output VDI3682:isCharacterizedBy ?output_id.
		?output_de DINEN61360:has_Instance_Description ?output_id;
				DINEN61360:has_Type_Description ?td.
		?output_id a ?dataType.
		OPTIONAL {
			?output_id DINEN61360:Value ?outputValue.
		}
		OPTIONAL {
			?capability CSS:isRestrictedBy ?equalConstraint.
			?equalConstraint OM:arguments/rdf:rest/rdf:first|OM:arguments/rdf:first ?input_id;
																		OM:arguments/rdf:rest/rdf:first|OM:arguments/rdf:first ?output_id;
																													OM:operator OM-Relation1:eq.
		}
	} """
	query_string = query_string.replace('{capability_iri}', capability_iri)
	query_handler = StateHandler().get_query_handler()
	results = query_handler.query(query_string)
	property_dictionary = StateHandler().get_property_dictionary()
	influences: List[CapabilityPropertyInfluence] = []
	for row in results: 
		# for happening in range(happenings): 
		# capDict.add_CapabilityOccurrence(str(row['cap']), "http://www.w3id.org/hsu-aut/cask#ProvidedCapability", happening, [], [])
		property_iri = str(row['output_de'])
		prop = property_dictionary.get_property(property_iri)
		if(not row.get('equalConstraint') and not row.get('outputValue')):
			continue
		if(row.get('equalConstraint')):
			if(not row.get('inputStateSubclass').eq(row.get('outputStateSubclass'))):
				# equalConstraint but with different product type / information in output it is a property change
				effect = PropertyChange.ChangeByExpression
			elif(str(row.get('inputExpressionGoal')) == 'Requirement' or str(row.get('inputExpressionGoal')) == 'Actual_Value'):
				# Case of requirements or actual values. In this case, prop has a constant value and output is set to equal
				effect = PropertyChange.NoChange
			elif(str(row.get('inputExpressionGoal')) == 'Variable'):
				# Case of no expression goal, i.e., free parameter. In this case, prop is changed to the free parameter
				effect = PropertyChange.ChangeByExpression
		else:
			if (row.get('outputValue') and row.get('outputValue') == (row.get('inputValue'))):
				# Simple case: both input and output have the same static value
				effect = PropertyChange.NoChange
			elif (row.get('outputValue') and not row.get('outputValue') == (row.get('inputValue'))):
				if str(row.get('outputValue')).lower() == "false":
					effect = PropertyChange.SetFalse
				elif str(row.get('outputValue')).lower() == "true":
					effect = PropertyChange.SetTrue
				else:
					# Numeric change
					effect = PropertyChange.NumericConstant

		influence = CapabilityPropertyInfluence(prop, effect)
		influences.append(influence)

	return influences