import json
import time
import gc
import ctypes

from typing import List

# Load libc for malloc_trim
try:
    libc = ctypes.CDLL("libc.so.6")
    libc.malloc_trim.argtypes = [ctypes.c_size_t]
    libc.malloc_trim.restype = ctypes.c_int
    MALLOC_TRIM_AVAILABLE = True
except:
    MALLOC_TRIM_AVAILABLE = False

from smt_planning.ontology_handling.query_handlers import FileQueryHandler, SparqlEndpointQueryHandler
from smt_planning.planning_result import PlanningResultType, PlanningResult
from smt_planning.dicts.PropertyDictionary import Property
# Hinzugefügt: AtMost für die minimale Kapazitäten-Suche
from z3 import Solver, Optimize, unsat, sat, unknown, Bool, Z3_OP_IMPLIES, Or, Not, And, AtMost
from smt_planning.smt.StateHandler import StateHandler
from smt_planning.openmath.parse_openmath import QueryCache
from smt_planning.smt.property_links import get_related_properties, set_required_capability, reset_property_pairs
from smt_planning.ontology_handling.related_inits import find_all_related_inits
from smt_planning.ontology_handling.capability_and_property_query import get_all_properties, get_provided_capabilities
from smt_planning.ontology_handling.init_query import get_init
from smt_planning.ontology_handling.capability_constraints_query import get_capability_constraints
from smt_planning.smt.variable_declaration import create_property_dictionary_with_occurrences, create_capability_dictionary_with_occurrences, create_resource_ids
from smt_planning.smt.capability_preconditions import capability_preconditions_smt
from smt_planning.smt.capability_effects import capability_effects_smt
from smt_planning.smt.capability_constraints import capability_constraints_smt
from smt_planning.smt.bool_variable_support import getPropositionSupports
from smt_planning.smt.constraints_bools import get_bool_constraints
from smt_planning.smt.constraints_real_variables import get_variable_constraints
from smt_planning.smt.init import init_smt
from smt_planning.smt.goal import goal_smt
from smt_planning.smt.real_variable_contin_change import get_real_variable_continuous_changes
from smt_planning.smt.capability_mutexes import get_capability_mutexes
from smt_planning.smt.fix_constants import fix_constants
from smt_planning.smt.bind_floating_vars import bind_floating_variables
# Entfernt: causal_links import (wir brauchen ihn nicht mehr)

class CaskadePlanner:

    required_capability_iri: str
    process_iri: str

    def __init__(self, required_capability_iri: str, process_iri: str | None = None) -> None:
        self.required_capability_iri = required_capability_iri
        self.process_iri = process_iri
        print(f"[PLANNER INIT] required_capability_iri: {required_capability_iri}")
        print(f"[PLANNER INIT] process_iri: {process_iri}")
        self.assertion_dictionary = {}  # Instance variable, not class variable!
        self.current_solver = None  # Track current solver for cancellation
        self._cancelled = False  # Track if planning was cancelled

    def cancel(self):
        """Cancel the current planning operation by interrupting the solver"""
        self._cancelled = True
        if self.current_solver is not None:
            print("Interrupting Z3 solver...")
            self.current_solver.interrupt()

    def with_file_query_handler(self, filename: str):
        self.query_handler = FileQueryHandler(filename)

    def with_endpoint_query_handler(self, endpoint_url):
        self.query_handler = SparqlEndpointQueryHandler(endpoint_url)

    def add_comment(self, solver: Solver, comment_text: str):
        # Adds a comment to the smt output in a pretty hackish way: 
        # Z3 doesn't allow adding comments, so we create a variable with the comment as its name and add it to the solver
        comment = Bool(f"## {comment_text} ##")
        solver.add(comment)

    def _extract_model_dict(self, model):
        """Extract model dictionary from Z3 model, converting all Z3 objects to Python native types"""
        replaced_model = {}
        for model_declaration in model.decls():
            declaration_name = model_declaration.name()
            if declaration_name in self.assertion_dictionary:
                continue
            else:
                value = model[model_declaration]
                value_type = str(model_declaration.range())

                # Convert Z3 values to Python native types for pickling
                if value_type == "Bool":
                    replaced_model[declaration_name] = bool(value)
                elif value_type == "Int":
                    replaced_model[declaration_name] = int(str(value))
                elif value_type == "Real":
                    # Convert Real to float using as_decimal for precision
                    decimal_str = value.as_decimal(20) if hasattr(value, 'as_decimal') else str(value)
                    # Remove approximation marker '?'
                    if decimal_str.endswith('?'):
                        decimal_str = decimal_str[:-1]
                    replaced_model[declaration_name] = float(decimal_str)
                else:
                    # Fallback: convert to string
                    replaced_model[declaration_name] = str(value)
        return replaced_model

    def _save_optional_outputs(self, result, solver, model, problem_location, model_location, plan_location):
        """Save optional output files"""
        if problem_location:
            # if problem_location is passed, store problem
            with open(problem_location, 'w') as file:
                file.write(solver.to_smt2())

        if model_location and model:
            # if model_location is passed, store model untransformed
            model_dict = {}
            for var in model:
                model_dict[str(var)] = str(model[var])
            with open(model_location, 'w') as file:
                json.dump(model_dict, file, indent=4)

        if plan_location:
            # if plan_location is passed, store model after transformation to better JSON
            with open(plan_location, 'w') as json_file:
                json.dump(result, json_file, default=lambda o: o.to_json(), indent=4)

    def cask_to_smt(self, max_happenings: int = 5, problem_location = None, model_location = None, plan_location = None, find_all_solutions: bool = False) -> PlanningResult:
        print("Started planning. This may take a while...")
        # Reset cancellation flag at start of each planning request
        self._cancelled = False
        self.current_solver = None

        start_time = time.time()
        state_handler = StateHandler()
        state_handler.set_query_handler(self.query_handler)
        reset_property_pairs()

        # Set required cap to property link finding. TODO: Could be better moved to state handler
        set_required_capability(self.required_capability_iri)

        happenings = 0
        # Fixed upper bound for number of events in one happening. Currently no events, so we just have the start and end of a happening
        event_bound = 2
        solver_result = unsat

        # needs to be reset for new planning request
        QueryCache.reset()
            
        # Get all properties connected to provided capabilities as inputs or outputs as well as all instance descriptions
        property_dictionary = get_all_properties(self.required_capability_iri)
        state_handler.set_property_dictionary(property_dictionary)
        find_all_related_inits()    # after all properties were assigned, add the related ones to the inits

        # Get provided capabilities and their influence on output objects as well as resources that provide capabilities
        cap_and_res_dictionary = get_provided_capabilities(self.required_capability_iri)
        capability_dictionary = cap_and_res_dictionary[0]
        resource_dictionary = cap_and_res_dictionary[1]
        state_handler.set_capability_dictionary(capability_dictionary)
        state_handler.set_resource_dictionary(resource_dictionary)

        # PRUNE capabilities by process AFTER all dictionaries are loaded
        if self.process_iri:
            print(f"[PRUNING] Starting pruning for process {self.process_iri}")
            capability_dictionary.prune_by_process(self.process_iri, self.query_handler)
            print(f"[PRUNING] Capability pruning complete. Remaining capabilities: {len(capability_dictionary.provided_capabilities)}")

            # Clean up dangling references in ResourceDictionary and PropertyDictionary
            resource_dictionary.prune_missing_capabilities(capability_dictionary)
            property_dictionary.prune_missing_capabilities(capability_dictionary)
            print("[PRUNING] Complete cleanup finished.")

        # Capability Constraints to store
        get_capability_constraints()
        
        # Get all inits and goals of planning problem based on the instance descriptions
        get_init()
        
        time_before_loop = time.time()
        print(f"Time for setup: {time_before_loop - start_time}")

        while (happenings < max_happenings and solver_result == unsat and not self._cancelled):
            time_loop_start = time.time()
            # SMT Solver
            solver = Solver()
            self.current_solver = solver  # Register for cancellation
            solver.set(unsat_core=True)
            solver.reset()
            
            solver_result = unsat
            happenings += 1

            # ------------------------------Variable Declaration------------------------------------------  
            # Get all properties connected to provided capabilities as inputs or outputs
            create_property_dictionary_with_occurrences(happenings, event_bound)

            time_after_prop_dict = time.time()
            print(f"Time for PropertyDictionary: {time_after_prop_dict - time_loop_start}")

            # Get provided capabilities and transform to boolean SMT variables
            create_capability_dictionary_with_occurrences(happenings)

            time_after_cap_dict = time.time()
            print(f"Time for CapabilityDictionary: {time_after_cap_dict - time_after_prop_dict}")

            # ------------------------------Ressource IDs---------------------------------------------------
            self.add_comment(solver, "Start of resource ids")
            resource_ids = create_resource_ids(happenings, event_bound)
            resource_id_counter = 0
            for resource_id in resource_ids:
                resource_id_counter += 1
                assertion_name = f'resourceId_{resource_id_counter}_{happenings}'
                self.assertion_dictionary[assertion_name] = resource_id
                solver.assert_and_track(resource_id, assertion_name)

            # ------------------------Constraint Proposition (H1 + H2) --> bool properties------------------
            self.add_comment(solver, "Start of constraints proposition")
            bool_constraints = get_bool_constraints(happenings, event_bound)
            bool_constraint_counter = 0
            for bool_constraint in bool_constraints:
                bool_constraint_counter += 1
                assertion_name = f'boolConstraint_{bool_constraint_counter}_{happenings}'
                self.assertion_dictionary[assertion_name] = bool_constraint
                solver.assert_and_track(bool_constraint, assertion_name)

            time_after_constraint_prop = time.time()
            print(f"Time for constraint proposition: {time_after_constraint_prop - time_after_cap_dict}")

            # ---------------------Constraint Real Variable (H5) --> real properties-----------------------------
            self.add_comment(solver, "Start of constraints real variables")
            variable_constraints = get_variable_constraints(happenings, event_bound)
            variable_constraint_counter = 0
            for variable_constraint in variable_constraints:
                variable_constraint_counter += 1
                assertion_name = f'varConstraint_{variable_constraint_counter}_{happenings}'
                self.assertion_dictionary[assertion_name] = variable_constraint
                solver.assert_and_track(variable_constraint, assertion_name)

            time_after_var_constraints = time.time()
            print(f"Time for var constraints: {time_after_var_constraints - time_after_constraint_prop}")

            # ----------------- Capability Precondition ------------------------------------------------------
            self.add_comment(solver, "Start of preconditions")
            precondition_constraints = capability_preconditions_smt(happenings, event_bound)
            precondition_counter = 0
            for precondition in precondition_constraints:
                precondition_counter += 1
                assertion_name = f'precond_{precondition_counter}_{happenings}'
                self.assertion_dictionary[assertion_name] = precondition
                solver.assert_and_track(precondition, assertion_name)

            time_after_preconds = time.time()
            print(f"Time for preconditions: {time_after_preconds - time_after_constraint_prop}")

            # --------------------------------------- Capability Effect ---------------------------------------
            self.add_comment(solver, "Start of effects")
            effects = capability_effects_smt(happenings, event_bound)
            effect_counter = 0
            for effect in effects:
                effect_counter += 1
                assertion_name = f'effect_{effect_counter}_{happenings}'
                self.assertion_dictionary[assertion_name] = effect
                solver.assert_and_track(effect, assertion_name)

            time_after_effects = time.time()
            print(f"Time for effects: {time_after_effects - time_after_preconds}")

            # ---------------- Constraints Capability mutexes (H14) -----------------------------------------
            self.add_comment(solver, "Start of capability mutexes")
            capability_mutexes = get_capability_mutexes(happenings)
            capability_mutex_counter = 0
            for capability_mutex in capability_mutexes:
                capability_mutex_counter += 1
                assertion_name = f'capMutex_{capability_mutex_counter}_{happenings}'
                self.assertion_dictionary[assertion_name] = capability_mutex
                solver.assert_and_track(capability_mutex, assertion_name)
            
            time_after_mutexes = time.time()
            print(f"Time for mutexes: {time_after_mutexes - time_after_effects}")

            # ---------------- Init  --------------------------------------------------------
            self.add_comment(solver, "Start of init")
            init_constraints = init_smt()
            init_counter = 0
            for init in init_constraints:
                init_counter += 1
                assertion_name = f'init_{init_counter}_{happenings}'
                self.assertion_dictionary[assertion_name] = init
                solver.assert_and_track(init, assertion_name)

            time_after_inits = time.time()
            print(f"Time for inits: {time_after_inits - time_after_mutexes}")

            # ---------------------- Goal ------------------------------------------------- 
            self.add_comment(solver, "Start of goal")
            goal_constraints = goal_smt(happenings)
            goal_counter = 0
            for goal in goal_constraints:
                goal_counter += 1
                assertion_name = f'goal_{goal_counter}_{happenings}'
                self.assertion_dictionary[assertion_name] = goal
                solver.assert_and_track(goal, assertion_name)

            time_after_goals = time.time()
            print(f"Time for goals: {time_after_goals - time_after_mutexes}")

            # ------------------- Proposition support (P5 + P6) ----------------------------
            self.add_comment(solver, "Start of proposition support")
            proposition_supports = getPropositionSupports(happenings, event_bound)
            suppport_counter = 0
            for support in proposition_supports:
                suppport_counter += 1
                assertion_name = f'support_{suppport_counter}_{happenings}'
                self.assertion_dictionary[assertion_name] = support
                solver.assert_and_track(support, assertion_name)
            
            time_after_prop_support = time.time()
            print(f"Time for prop support: {time_after_prop_support - time_after_goals}")

            # ----------------- Continuous change on real variables (P11) ------------------
            self.add_comment(solver, "Start of real variable continuous change")
            real_variable_cont_changes = get_real_variable_continuous_changes(happenings, event_bound)
            real_variable_cont_change_counter = 0
            for real_variable_cont_change in real_variable_cont_changes:
                real_variable_cont_change_counter += 1
                assertion_name = f'realVarContChange_{real_variable_cont_change_counter}_{happenings}'
                self.assertion_dictionary[assertion_name] = real_variable_cont_change
                solver.assert_and_track(real_variable_cont_change, assertion_name)

            time_after_realVarContChange = time.time()
            print(f"Time for real var conti change: {time_after_realVarContChange - time_after_prop_support}")

            # Capability constraints are expressions in smt2 form that cannot be added programmatically...
            self.add_comment(solver, "Start of capability constraints")

            if problem_location:
                with open(problem_location, 'w', encoding='utf-8') as file:
                    file.write(solver.to_smt2())

            temp_solver = Solver()
            # Add property z3 variables
            temp_solver_string = "\n".join(
                [f'(declare-fun {occurrence.z3_variable.sexpr()} () {occurrence.type})' for occurrence in property_dictionary.get_all_property_occurences()]
            )
            # Add capability z3 variables
            temp_solver_string += "\n".join(
                [f'(declare-fun {occurrence.z3_variable.sexpr()} () Bool)' for occurrence in capability_dictionary.get_all_capability_occurrences()]
            )
            # Add constraints
            constraints = capability_constraints_smt(happenings, event_bound)
            for constraint in constraints:
                temp_solver_string += f"\n{constraint}"

            # Debug: Save solver string before parsing
            import sys
            lines = temp_solver_string.split('\n')
            if len(lines) >= 1863:
                sys.stderr.write(f"=== DEBUG: Line 1861-1865 ===\n")
                for i in range(max(0, 1860), min(len(lines), 1866)):
                    sys.stderr.write(f"Line {i+1}: {lines[i]}\n")
                sys.stderr.flush()

            temp_solver.from_string(temp_solver_string)
            temp_solver_assertions = temp_solver.assertions()

            # add all assertions back into main solver, now with tracking
            cap_constraint_counter = 0
            for capability_constraint_assertion in temp_solver_assertions:
                cap_constraint_counter += 1
                assertion_name = f'capConstraint_{cap_constraint_counter}_{happenings}'
                self.assertion_dictionary[assertion_name] = capability_constraint_assertion
                solver.assert_and_track(capability_constraint_assertion, assertion_name)

            time_after_cap_constraints = time.time()
            print(f"Time for cap constraints: {time_after_cap_constraints - time_after_realVarContChange}")

            self.add_comment(solver, "Start of constants")
            constant_expressions = fix_constants(property_dictionary, capability_dictionary, happenings, event_bound)
            constant_counter = 0
            for constant_expression in constant_expressions:
                constant_counter += 1
                assertion_name = f'constant_{constant_counter}'
                self.assertion_dictionary[assertion_name] = constant_expression
                solver.assert_and_track(constant_expression, assertion_name)
                
            time_after_constants = time.time()
            print(f"Time for constants: {time_after_constants - time_after_cap_constraints}")
            
            self.add_comment(solver, "Start of floating variable bindings")
            binding_expressions = bind_floating_variables()
            binding_counter = 0
            for binding_expression in binding_expressions:
                binding_counter += 1
                assertion_name = f'binding_{binding_counter}'
                self.assertion_dictionary[assertion_name] = binding_expression
                solver.assert_and_track(binding_expression, assertion_name)
                    
            time_after_binding_floating_values = time.time()
            print(f"Time for binding free values: {time_after_binding_floating_values - time_after_constants}")

            end_time = time.time()
            print(f"Time for generating SMT overall: {end_time - start_time}")  
            print(f"Time for generating this happening: {end_time - time_loop_start}")  

            # Check satisfiability and get the model
            solver_result = solver.check()
            end_time_solver = time.time()
            print(f"Number of Assertions: {len(solver.assertions())}")
            print(f"Time for solving SMT: {end_time_solver - end_time}")

            # Check if solver was interrupted/cancelled
            if solver_result == unknown:
                reason = solver.reason_unknown()
                print(f"Solver returned unknown: {reason}")
                if "interrupt" in reason.lower() or "canceled" in reason.lower() or self._cancelled:
                    print("Planning was cancelled")
                    return None

            if solver_result == unsat:
                print(f"No solution with {happenings} happening(s) found.")
                if MALLOC_TRIM_AVAILABLE:
                    libc.malloc_trim(0)
            else:
                # --------------------- ITERATIVE DEEPENING & MINIMIZATION ---------------------
                # Der Solver hat die erste funktionierende Lösung gefunden (z.B. mit 6 Capabilities).
                # Wir zwingen ihn nun iterativ mit AtMost(), den absolut kürzesten Weg zu finden!
                print(f"Initial SAT found at {happenings} happenings. Minimizing capability usage...")
                
                capability_dictionary = state_handler.get_capability_dictionary()
                all_cap_vars = []
                for cap in {**capability_dictionary.provided_capabilities, **capability_dictionary.required_capabilities}.values():
                    for occ in cap.occurrences.values():
                        all_cap_vars.append(occ.z3_variable)
                        
                if all_cap_vars:
                    model = solver.model()
                    current_min = sum(1 for v in all_cap_vars if str(model.eval(v, model_completion=True)) in ['True', 'true'])
                    print(f"Initial solution uses {current_min} capabilities.")

                    # Wir verkleinern das Budget, bis Z3 den Weg nicht mehr findet
                    while current_min > 0 and not self._cancelled:
                        solver.push()
                        solver.add(AtMost(*all_cap_vars, current_min - 1))
                        if solver.check() == sat:
                            model = solver.model()
                            current_min = sum(1 for v in all_cap_vars if str(model.eval(v, model_completion=True)) in ['True', 'true'])
                            print(f"Found tighter solution with ONLY {current_min} capabilities!")
                            solver.pop() # Wir verwerfen das aktuelle AtMost, um im nächsten Schritt ein noch engeres zu setzen
                        else:
                            solver.pop() # Lösung ist mit current_min - 1 nicht mehr möglich
                            break
                    
                    print(f"Absolute minimal capability count is {current_min}. Locking search space.")
                    solver.add(AtMost(*all_cap_vars, current_min))
                    # Ein letzter check(), um das Modell wieder auf den garantierten minimalen Pfad zu setzen
                    solver.check()
                # ------------------------------------------------------------------------------

                if not find_all_solutions:
                    model = solver.model()
                    replaced_model = self._extract_model_dict(model)
                    result = PlanningResult(PlanningResultType.SAT, replaced_model, None)
                    self._save_optional_outputs(result, solver, model, problem_location, model_location, plan_location)
                    return result
                else:
                    all_models_data = []
                    solution_count = 0

                    while solver.check() == sat and not self._cancelled:
                        solution_count += 1
                        model = solver.model()
                        replaced_model = self._extract_model_dict(model)
                        all_models_data.append(replaced_model)

                        current_true_vars = [v for v in all_cap_vars if str(model.eval(v, model_completion=True)) in ['True', 'true']]
                        print(f"Found structurally minimal solution {solution_count} with EXACTLY {len(current_true_vars)} capabilities.")
                        
                        if current_true_vars:
                            # Verbiete diese Kombination, um die nächste (genauso kurze) Alternative zu finden
                            solver.add(Not(And(*current_true_vars)))
                        else:
                            break
                            
                        if solution_count >= 15:
                            print("Reached limit of 15 minimal solutions - stopping search.")
                            break

                    if self._cancelled:
                        return None

                    if all_models_data:
                        res_type = PlanningResultType.SAT if len(all_models_data) == 1 else PlanningResultType.MULTIPLE_SAT
                        result = PlanningResult(res_type, all_models_data[0] if len(all_models_data) == 1 else None, None, all_models_data)
                        self._save_optional_outputs(result, solver, None, problem_location, model_location, plan_location)
                        return result
                    
                    return None
        
        unsat_core = solver.unsat_core()
        transformed_unsat_core = []
        for core in unsat_core:
            core_elem = self.assertion_dictionary[str(core)]
            transformed_unsat_core.append(core_elem)

        if len(transformed_unsat_core) < 10:
            muc = find_minimal_unsat_core(transformed_unsat_core)
        else:
            print(f"Unsat core too large ({len(transformed_unsat_core)} elements), skipping MUC computation")
            muc = transformed_unsat_core  
        unsat_core_string = []
        for core in muc:
            unsat_core_string.append(str(core))
        result = PlanningResult(PlanningResultType.UNSAT, None, unsat_core_string)
        end_time_muc = time.time()
        print(f"Time for finding MUC: {end_time_muc - end_time_solver}")
        return result

def is_unsat_core(core):
    s = Solver()
    for c in core:
        s.add(c)
    return s.check() == unsat

def find_minimal_unsat_core(core):
    if not is_unsat_core(core):
        return core
    
    for i in range(len(core)):
        reduced_core = core[:i] + core[i+1:]
        if is_unsat_core(reduced_core):
            return find_minimal_unsat_core(reduced_core)
    
    return core

def find_variable_in_expression(expression, variable):
    if any(child.decl().kind() == Z3_OP_IMPLIES for child in expression.children()) :
        return False
    if expression == variable:
        return True
    return any(find_variable_in_expression(child, variable) for child in expression.children())

def is_variable_asserted(solver, variable):
    for assertion in solver.assertions():
        if find_variable_in_expression(assertion, variable):
            return True
    return False