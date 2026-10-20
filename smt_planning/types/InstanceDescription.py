'''
iri is the IRI of the data element
cap_iri is the IRI of the capability
expr_goal is the DINEN61360:Expression_Goal of the instance description
logical_interpretation is the DINEN61360:Logical_Interpretation of the instance description
value is the DINEN61360:Value of the instance description
'''
class InstanceDescription:
	def __init__(self, data_element_iri: str, cap_iri: str, expr_goal: str, logical_interpretation: str, value: str):
		self.iri = data_element_iri
		self.cap_iri = cap_iri
		self.expr_goal = expr_goal
		self.logical_interpretation = logical_interpretation
		self.value = value

	def __eq__(self, other):
		if not isinstance(other, InstanceDescription):
			# catch invalid comparisons
			return NotImplemented
		return (
			self.iri == other.iri and
			self.expr_goal == other.expr_goal and
			self.logical_interpretation == other.logical_interpretation and
			self.value == other.value
		)
    
	def __hash__(self):
		return hash((self.iri, self.expr_goal, self.logical_interpretation, self.value))


# InstanceDescription of a DataElement with DINEN61360:Expression_Goal "Requirement"
class Precondition(InstanceDescription):
	def __init__(self, iri: str, cap_iri: str, logical_interpretation: str, value: str) -> None:
		super().__init__(iri, cap_iri, "Requirement", logical_interpretation, value)

# InstanceDescription of a DataElement with DINEN61360:Expression_Goal "Assurance"
class Effect(InstanceDescription):
	def __init__(self, iri: str, cap_iri: str, logical_interpretation: str, value: str) -> None:
		super().__init__(iri, cap_iri, "Assurance", logical_interpretation, value)

class Init(InstanceDescription):
	def __init__(self, iri: str, cap_iri: str, logical_interpretation: str, value: str) -> None:
		super().__init__(iri, cap_iri, "Actual_Value", logical_interpretation, value)

class ResourceConfiguration(InstanceDescription):
	def __init__(self, iri: str, cap_iri: str, logical_interpretation: str, value: str) -> None:
		super().__init__(iri, cap_iri, "Actual_Value", logical_interpretation, value)

class Goal(InstanceDescription):
	def __init__(self, iri: str, cap_iri: str, logical_interpretation: str, value: str) -> None:
		super().__init__(iri, cap_iri, "Requirement", logical_interpretation, value)

class FreeVariable(InstanceDescription):
	def __init__(self, iri: str, cap_iri: str, logical_interpretation: str) -> None:
		super().__init__(iri, cap_iri, "Free_Variable", logical_interpretation, "")