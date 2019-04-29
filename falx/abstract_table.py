import json
import copy
from pprint import pprint



class AbstractTable(object):

	def __init__(self, values, constraints):
		"""constraints should be of form 
			Args:
				values: a list of named tuples representing values 
					that should be contained by the abstract table
					e.g. {["a": 1, "b": 2, "c": 100],
					 	  ["a": 2, "b"; 5, "c": 15]} 
					 contains two tuples
				constraints:
					forall r in T. p(t)
					exists r in T. p(t)
					p(column) 
		"""

		self.values = exist_values
		self.constraints = constraints

	def __str__(self):
		return self.values.__str__()