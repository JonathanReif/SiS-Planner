from typing import List
from z3 import BoolRef, Implies, Or, And

from smt_planning.smt.StateHandler import StateHandler


def get_causal_link_constraints(happenings: int) -> List[BoolRef]:
    """
    Enforce causal links: A capability can only be active if at least one of its outputs
    is either (1) part of the goal OR (2) consumed by another active capability.

    This prevents "spurious actions" or "dead ends" where capabilities are activated
    but their outputs are never used.
    """
    constraints = []

    state_handler = StateHandler()
    capability_dictionary = state_handler.get_capability_dictionary()
    property_dictionary = state_handler.get_property_dictionary()

    # Get goal property IRIs
    goal_property_iris = set(property_dictionary.goals.keys())

    # For each happening and each capability
    for happening in range(happenings):
        for cap_iri, capability in capability_dictionary.provided_capabilities.items():
            if happening not in capability.occurrences:
                continue

            cap_var = capability.occurrences[happening].z3_variable

            # Find all outputs of this capability (effects)
            output_property_iris = []
            for prop_iri, effect_set in property_dictionary.effects.items():
                for effect in effect_set:
                    if effect.cap_iri == cap_iri:
                        output_property_iris.append(prop_iri)
                        break

            if not output_property_iris:
                # No outputs means this capability doesn't produce anything
                # In a proper model this shouldn't happen, but we skip it
                continue

            # For each output, check if it's useful
            useful_conditions = []

            for out_prop_iri in output_property_iris:
                # Condition 1: Output is a goal
                if out_prop_iri in goal_property_iris:
                    useful_conditions.append(True)  # Always useful
                    continue

                # Condition 2: Output is consumed directly by another capability
                consumed_by_caps = []
                if out_prop_iri in property_dictionary.preconditions:
                    for precondition in property_dictionary.preconditions[out_prop_iri]:
                        consuming_cap_iri = precondition.cap_iri
                        if consuming_cap_iri == cap_iri:
                            continue  # Skip self-consumption
                        consumed_by_caps.append(consuming_cap_iri)

                # Condition 3: Output's related properties are consumed by another capability
                from smt_planning.smt.property_links import get_related_properties
                related_props = get_related_properties(out_prop_iri)
                for related_prop in related_props:
                    if related_prop.iri in property_dictionary.preconditions:
                        for precondition in property_dictionary.preconditions[related_prop.iri]:
                            consuming_cap_iri = precondition.cap_iri
                            if consuming_cap_iri == cap_iri:
                                continue  # Skip self-consumption
                            if consuming_cap_iri not in consumed_by_caps:
                                consumed_by_caps.append(consuming_cap_iri)

                # Add constraints for future happenings where consuming caps might be active
                for future_happening in range(happening + 1, happenings):
                    for consuming_cap_iri in consumed_by_caps:
                        if consuming_cap_iri in capability_dictionary.provided_capabilities:
                            consuming_cap = capability_dictionary.provided_capabilities[consuming_cap_iri]
                            if future_happening in consuming_cap.occurrences:
                                consuming_cap_var = consuming_cap.occurrences[future_happening].z3_variable
                                useful_conditions.append(consuming_cap_var)

            if not useful_conditions:
                # No outputs are useful - this capability should NEVER be active
                from z3 import Not
                constraint = Not(cap_var)
                constraints.append(constraint)
            else:
                # If capability is active, at least one of its outputs must be useful
                # Implies(cap_var, Or(useful_conditions))
                constraint = Implies(cap_var, Or(useful_conditions))
                constraints.append(constraint)

    return constraints
