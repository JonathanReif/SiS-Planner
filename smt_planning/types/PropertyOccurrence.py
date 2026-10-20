from smt_planning.dicts.name_util import convert_iri_to_z3_variable
from z3 import Real, Bool, Int

# data_type is some instance of http://www.w3id.org/hsu-aut/DINEN61360#Simple_Data_Type
class PropertyOccurrence:
	def __init__(self, iri: str, data_type: str, happening: int, event: int):
		self.iri = iri
		self.happening = happening
		self.event = event
		z3_variable_name = convert_iri_to_z3_variable(iri, happening, event)
		match data_type:
			case "http://www.w3id.org/hsu-aut/DINEN61360#Real":
				self.z3_variable = Real(z3_variable_name)
				self.type = "Real"
			case "http://www.w3id.org/hsu-aut/DINEN61360#Boolean":
				self.z3_variable = Bool(z3_variable_name)
				self.type = "Bool"
			case "http://www.w3id.org/hsu-aut/DINEN61360#Integer":
				self.z3_variable = Int(z3_variable_name)
				self.type = "Int"
			case _  :
				# Base case if no type given: Create a real
				self.z3_variable = Real(z3_variable_name)
				self.type = "Real"