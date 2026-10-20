from smt_planning.smt.StateHandler import StateHandler
from smt_planning.dicts.PropertyDictionary import CapabilityType
		
def get_init():
	
	query_string = """
		PREFIX DINEN61360: <http://www.w3id.org/hsu-aut/DINEN61360#>
		PREFIX CSS: <http://www.w3id.org/hsu-aut/css#>
		PREFIX CaSk: <http://www.w3id.org/hsu-aut/cask#>
		PREFIX VDI3682: <http://www.w3id.org/hsu-aut/VDI3682#>
		SELECT DISTINCT ?de ?log ?val WHERE { 
			?de a DINEN61360:Data_Element.
			?de DINEN61360:has_Instance_Description ?id.
			?id DINEN61360:Expression_Goal "Actual_Value";
				DINEN61360:Logic_Interpretation ?log;
				DINEN61360:Value ?val. 
			?de DINEN61360:has_Instance_Description ?id2. 
			?cap a CaSk:ProvidedCapability; 
				^CSS:requiresCapability ?process.
			?process ?relation ?inout.
			VALUES ?relation { VDI3682:hasInput VDI3682:hasOutput }.
			?inout VDI3682:isCharacterizedBy ?id2.
		}  """
	stateHandler = StateHandler()
	query_handler = stateHandler.get_query_handler()
	property_dictionary = stateHandler.get_property_dictionary()
	results = query_handler.query(query_string)
	for row in results:
		property_dictionary.add_instance_description(str(row['de']), "", CapabilityType.ProvidedCapability, "Actual_Value", str(row['log']), str(row['val']))
		