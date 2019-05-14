import json
import copy
from pprint import pprint


class SymVal(object):
	""" symbolic value"""
	id_counter = 0

	def __init__(self, id, ty):
		self.id = id
		self.ty = ty

	@classmethod
	def get_fresh_name(cls):
		current_id = cls.id_counter
		cls.id_counter += 1
		return current_id

class SymTable(object):

	def __init__(self, values, constraints=None):
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
		self.values = values
		self.constraints = constraints

	def get_schema(self):
		"""get schema of the table """
		if len(self.values) > 0:
			return self.values[0].keys()
		return None

	def consistent_with(table):
		"""Check if the given table is consistent with the symbolic table """
		return True

	def instantiate(self):
		"""a naive instantiation that simply returns all values"""
		return self.values

	def __str__(self):
		return self.values.__str__()