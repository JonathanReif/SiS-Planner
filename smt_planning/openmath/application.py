from rdflib import URIRef
from typing import List

class Application:
    argType = URIRef("http://openmath.org/vocab/math#Application")

    def __init__(self, context, application, position, operator, argName, argValue, args=None):
        self.context = context
        self.application = application
        self.position = position
        self.operator = operator
        self.argName = argName
        self.argValue = argValue
        self.args = args if args is not None else []

    def add_arg(self, arg):
        self.args.append(arg)
