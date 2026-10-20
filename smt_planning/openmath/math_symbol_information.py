class MathSymbolInformation:
	symbol: str
	arity = 1 | 2

	def __init__(self, symbol: str, arity = 1|2):
		self.symbol = symbol
		self.arity = arity