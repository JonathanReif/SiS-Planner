from typing import List

from smt_planning.smt.StateHandler import StateHandler
from smt_planning.openmath.parse_openmath import from_open_math_in_graph

def capability_constraints_smt(happenings: int, event_bound: int) -> List[str]:	
	query_handler = StateHandler().get_query_handler()
	capability_dictionary = StateHandler().get_capability_dictionary()
	constraint_assertions = []
	for happening in range(happenings):
		for constraint_info in capability_dictionary.input_capability_constraints:
			current_capability = capability_dictionary.get_capability_occurrence(constraint_info.cap, happening).z3_variable
			# Debug logging disabled to reduce log spam
			# print(f"DEBUG: Loading INPUT constraint for capability: {constraint_info.cap}, constraint IRI: {constraint_info.constraintIri}")
			infix_constraint = from_open_math_in_graph(query_handler, constraint_info.constraintIri, happening, 0)
			prefix_expression = infix_to_prefix(infix_constraint)
			assertion = f"(assert (=> {(current_capability.sexpr())} {prefix_expression}))"
			constraint_assertions.append(assertion)
		for constraint_info in capability_dictionary.output_capability_constraints:
			current_capability = capability_dictionary.get_capability_occurrence(constraint_info.cap, happening).z3_variable
			# Debug logging disabled to reduce log spam
			# print(f"DEBUG: Loading OUTPUT constraint for capability: {constraint_info.cap}, constraint IRI: {constraint_info.constraintIri}")
			infix_constraint = from_open_math_in_graph(query_handler, constraint_info.constraintIri, happening, 1)
			prefix_expression = infix_to_prefix(infix_constraint)
			assertion = f"(assert (=> {(current_capability.sexpr())} {prefix_expression}))"
			constraint_assertions.append(assertion)

	return constraint_assertions



def infix_to_prefix(infix_expression):
    precedence_levels = {
        'or': 0,
        'and': 1,
        '=': 2,
        '>': 2,
        '>=': 2,
        '<': 2,
        '<=': 2,
        'distinct': 2,
        '+': 3,
        '-': 3,
        '*': 4,
        '/': 4,
        '^': 5
    }
    
    def precedence(operator):
        return precedence_levels.get(operator, -1)

    def is_operator(c):
        return c in precedence_levels

    def infix_to_postfix(expression):
        stack = []
        output = []
        
        tokens = expression.split()
        
        for token in tokens:
            if is_operator(token):
                while stack and precedence(stack[-1]) >= precedence(token):
                    output.append(stack.pop())
                stack.append(token)
            elif token == '(':
                stack.append(token)
            elif token == ')':
                while stack and stack[-1] != '(':
                    output.append(stack.pop())
                stack.pop()  # Remove '(' from the stack
            else:
                output.append(token)
        
        while stack:
            output.append(stack.pop())
        
        return output

    def postfix_to_prefix(postfix_expression):
        stack = []
        
        for token in postfix_expression:
            if not is_operator(token):
                stack.append(token)
            else:
                # It's an operator; pop two operands from the stack
                operand1 = stack.pop()
                operand2 = stack.pop()
                
                # Combine them in prefix form
                new_expr = f"({token} {operand2} {operand1})"
                stack.append(new_expr)
        
        return stack[0]

    postfix_expr = infix_to_postfix(infix_expression)
    prefix_expr = postfix_to_prefix(postfix_expr)
    
    return prefix_expr
