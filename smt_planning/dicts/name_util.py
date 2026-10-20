# Define separators for happenings and events
HAPPENING_SEPARATOR = "_"
EVENT_SEPARATOR = "_"

class Z3_Name_Components:
	def __init__(self, iri: str, happening:int, event:int):
		self.iri = iri
		self.happening = happening
		self.event = event

# Converts an IRI to a z3 variable by appending happening and event separated by the defined separators
def convert_iri_to_z3_variable(iri: str, happening: int, event: int = 0) -> str:
	z3_variable = f"{iri}{HAPPENING_SEPARATOR}{happening}{EVENT_SEPARATOR}{event}"
	return z3_variable


# Converts a z3 variable to an IRI by stripping everything that is behind event and happening separator
def convert_z3_variable_to_iri(z3_variable: str) -> Z3_Name_Components:
	stripped_string = z3_variable.strip("|")
	# Finde Positions of the separaors (we need to start from right as they can also be part of the IRI)
	last_event_sep_pos = stripped_string.rfind(EVENT_SEPARATOR)  # Last event separator char (i.e., the real event separator)
	last_happening_sep_pos = stripped_string.rfind(HAPPENING_SEPARATOR, 0, last_event_sep_pos)  # Last happening separator before the event separator (i.e. the real happening separator)

	# Extract parts based on position
	iri = stripped_string[:last_happening_sep_pos]
	happening = stripped_string[last_happening_sep_pos + 1:last_event_sep_pos]
	event = stripped_string[last_event_sep_pos + 1:]
	components = Z3_Name_Components(iri, int(happening), int(event))
	return components