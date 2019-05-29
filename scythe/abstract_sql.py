import json
import os

class AbsSQL(object):
	def __init__(self):
		pass
	
	def is_abstract(self):
		return True
	
	def get_schema(self):
        raise NotImplementedError
	
	def get_qualified_fields(self):
        name, fields = self.get_schema()
        return ["{}.{}".format(name, f) for f in fields]

class AbsSelect(AbsSQL):
	def __init__(self, q):
		self.q = q

	def eval(self):
		table = self.q.eval()
		return res

class AbsJoin(AbsSQL):
	def __init__(self, q1, q2):
		self.q1 = q1
		self.q2 = q2

	def eval(self):
		schema1, t1 = self.q1.get_qualified_fields(), self.q1.eval()
		schema2, t2 = self.q2.get_qualified_fields(), self.q2.eval()
		res = [r1 + r2 for r2 in t2 for r1 in t1]
		return res

class AbsAggr(AbsSQL):
	def __init__(self, q, gb_fields, targets):
		"""gb_fields is a list of columns
			targets is a list of (aggr_function, columns, new_name) pairs
		"""
		assert(not self.q.is_abstract())
		self.q = q
		self.gb_fields = gb_fields
		self.targets = targets

	def get_schema(self):
		return (None, None)

	def eval(self):
		schema, table = self.q.get_qualified_fields(), self.q.eval()
		groups = {}
		for r in table:
			binding = {s:r[i] for i, s in enumerate(schema)}
			gb_vals = tuple([f.eval(binding) for f in self.gb_fields])
			if gb_vals not in groups:
				groups[gb_vals] = []
			groups[gb_vals].append(r)

		res = []
		for gb_vals in groups:
			aggr_vals = []
			for aggr_func, target_col, _ in self.targets:
				vals = [target_col.eval({s:r[i] for i, s in enumerate(schema)}) for r in groups[gb_vals]]
				aggr_vals.append(aggr_func(vals))
			res.append(list(gb_vals) + aggr_vals)
		return res

class AbsUnion(AbsSQL):
	def __init__(self, q1, q2):
		self.q1 = q1
		self.q2 = q2

	def eval(self):
		return self.q1.eval() + self.q2.eval()

class AbsLeftJoin(AbsSQL):
	def __init__(self, q1, q2):
		assert(not self.q2.is_abstract())
		self.q1 = q1
		self.q2 = q2

	def eval(self):
		# approximating join pred
		schema1, t1 = self.q1.get_qualified_fields(), self.q1.eval()
		schema2, t2 = self.q2.get_qualified_fields(), self.q2.eval()
		res = []
		for r1 in t1:
			r1_used = False
			for r2 in t2:
				res.append(r1 + r2)
			# if there is no matching column, add it with null fields
			res.append(r1 + [None for i in range(len(schema2))])
		return res

class AbsAs(AbsSQL):
	def __init__(self, q, tname, fields):
		self.q = q
		self.name = name
		self.fields = fields

	def get_schema(self):
		return (self.name, self.fields)

	def eval(self):
		return self.q.eval()
