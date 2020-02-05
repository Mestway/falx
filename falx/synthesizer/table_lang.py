import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from falx.synthesizer.utils import HOLE
import copy

def get_fresh_col(used_columns, n=1):
	"""get a fresh column name used in pandas evaluation"""
	names = []
	for i in range(0, 1000):
		if "COL_{}".format(i) not in used_columns:
			names.append("COL_{}".format(i))
		if len(names) >= n:
			break
	return names

def get_temp_var(used_vars):
	"""get a temp variable name """
	for i in range(0, 1000):
		var_name = "t{}".format(i)
		if var_name not in used_vars:
			return var_name

def value_to_dict(val, val_type):
	"""given the value and its type, dump it to a dict 
		the helper function to dump values into dict ast
	"""
	return {"type": val_type, "value": val}

class Node(ABC):
	def __init__(self):
		super(AbstractExpression, self).__init__()

	@abstractmethod
	def eval(self):
		pass

	@abstractmethod
	def to_dict(self):
		pass

	@staticmethod
	def load_from_dict(ast):
		"""given a dictionary represented AST, load it in to a program form"""
		constructors = {
			"select": Select, "unite": Unite,
			"filter": Filter, "separate": Separate,
			"spread": Spread, "gather": Gather,
			"gather_neg": GatherNeg, "group_sum": GroupSummary,
			"cumsum": CumSum, "mutate": Mutate,
			"mutate_custom": MutateCustom,
		}
		if ast["op"] == "table_ref":
			return Table(ast["args"][0]["value"])
		else:
			node = constructors[ast["op"]](
						Node.load_from_dict(ast["args"][0]), 
						*[arg["value"] for arg in ast["args"][1:]])
			return node

	def to_stmt_dict(self):
		"""translate the expression into a  """
		def _recursive_translate(ast, used_vars):
			if ast["op"] == "table_ref":
				# create a variable to capture the return variable
				stmt_dict = copy.copy(ast)
				var = get_temp_var(used_vars)
				stmt_dict["return_as"] = var
				return [stmt_dict], used_vars + [var]
			else:
				stmt_dict = copy.copy(ast)

				# iterate over all possible subtrees
				sub_tree_stmts = []	
				for i, arg in enumerate(ast["args"]):
					# check if the argument is an ast 
					if isinstance(arg, (dict,)) and arg["type"] == "node":
						stmts, used_vars = _recursive_translate(ast["args"][0], used_vars)
						sub_tree_stmts += stmts
						# the subtree is replaced by a reference to the variable
						retvar = stmts[-1]["return_as"]
						stmt_dict["args"][i] = {"value": retvar, "type": "variable"}
				
				# use a temp variable to wrap the current statement, and add it to the coolection
				var = get_temp_var(used_vars)
				stmt_dict["return_as"] = var
				return sub_tree_stmts + [stmt_dict], used_vars + [var]

		stmts, _ = _recursive_translate(self.to_dict(), [])
		return stmts

	def is_abstract(self):
		"""Check if the subtree is abstract:
			if Hole or "c{}".format(Hole) is in the expression, it is considered abstract"""
		args = self.to_stmt_dict()[-1]["args"]

		return any([x == "?" 
					or (isinstance(x, (list,)) and any([v == "?" for v in x]))
					for stmt in self.to_stmt_dict() for x in stmt["args"]])
	
	def stmt_string(self):
		"""generate a string from stmts """
		stmts = self.to_stmt_dict()
		result = []
		for s in stmts:
			lhs = s['return_as']
			f = s['op']
			arg_str = ', '.join(['(' + ','.join(x['value']) + ')' if isinstance(x['value'],(list,tuple,)) 
						else str(x['value']) for x in s['args']])
			result.append(f"{lhs} <- {f}({arg_str})")

		return "; ".join(result)


class Table(Node):
	def __init__(self, data_id):
		self.data_id = data_id

	def eval(self, env):
		return env[self.data_id]

	def to_dict(self):
		return {
			"type": "node",
			"op": "table_ref",
			"args": [
				value_to_dict(self.data_id, "table_id")
			]
		}


class Select(Node):
	def __init__(self, q, cols):
		self.q = q
		self.cols = cols

	def eval(self, env):
		df = self.q.eval(env)
		return df[[df.columns[i] for i in self.cols]]

	def to_dict(self):
		return {
			"type": "node",
			"op": "select",
			"args": [self.q.to_dict(), value_to_dict(self.cols, "col_index_list")]
		}


class Unite(Node):
	def __init__(self, q, col1, col2):
		""" col1, col2 are column indexes"""
		self.q = q
		self.col1 = col1
		self.col2 = col2

	def eval(self, env):
		df = self.q.eval(env)
		ret = df.copy()
		new_col = get_fresh_col(list(ret.columns))[0]
		c1, c2 = ret.columns[self.col1], ret.columns[self.col2]
		ret[new_col] = ret[c1] + "_" + ret[c2]
		ret = ret.drop(columns=[c1, c2])
		return ret

	def to_dict(self):
		return {
			"type": "node",
			"op": "unite",
			"args": [
				self.q.to_dict(), 
				value_to_dict(self.col1, "col_index"), 
				value_to_dict(self.col2, "col_index")]}


class Filter(Node):
	def __init__(self, q, col_index, op, const):
		self.q = q
		self.col_index = col_index
		self.op = op
		self.const = const

	def eval(self, env):
		df = self.q.eval(env)
		col = df.columns[self.col_index]
		if self.op == "==":
			return df[df[col] == self.const].reset_index()
		elif self.op == "!=":
			return df[df[col] != self.const].reset_index()
		else:
			sys.exit(-1)

	def to_dict(self):
		return {
			"type": "node",
			"op": "filter",
			"args": [
				self.q.to_dict(), 
				value_to_dict(self.col_index, "col_index"), 
				value_to_dict(self.op, "binop"), 
				value_to_dict(self.const, "constant")
			]}


class Separate(Node):
	def __init__(self, q, col_index):
		self.q = q
		self.col_index = col_index

	def eval(self, env):
		df = self.q.eval(env)
		ret = df.copy()
		col = ret.columns[self.col_index]
		splitted = ret[col].str.split(r"\s|_", n=1, expand=True)
		new_col_names = get_fresh_col(list(ret.columns), n=2)
		ret[new_col_names[0]] = splitted[0]
		ret[new_col_names[1]] = splitted[1]
		ret = ret.drop(columns=[col])
		return ret

	def to_dict(self):
		return {
			"type": "node",
			"op": "separate",
			"args": [self.q.to_dict(), value_to_dict(self.col_index, "col_index")]
		}


class Spread(Node):
	def __init__(self, q, key, val):
		self.q = q
		self.key = key
		self.val = val
	
	def eval(self, env):
		def multiindex_pivot(df, columns=None, values=None):
			# a helper function for performing multi-index pivoting
		    #https://github.com/pandas-dev/pandas/issues/23955
		    names = list(df.index.names)
		    df = df.reset_index()
		    list_index = df[names].values
		    tuples_index = [tuple(i) for i in list_index] # hashable
		    df = df.assign(tuples_index=tuples_index)
		    df = df.pivot(index="tuples_index", columns=columns, values=values)
		    tuples_index = df.index  # reduced
		    index = pd.MultiIndex.from_tuples(tuples_index, names=names)
		    df.index = index
		    return df
		df = self.q.eval(env)
		key_col, val_col = df.columns[self.key], df.columns[self.val]
		index_cols = [c for c in list(df.columns) if c not in [key_col, val_col]]
		ret = df.set_index(index_cols)
		ret = multiindex_pivot(ret, columns=key_col, values=val_col).reset_index()
		return ret

	def to_dict(self):
		return {
			"type": "node",
			"op": "spread",
			"args": [
				self.q.to_dict(), 
				value_to_dict(self.key, "col_index"), 
				value_to_dict(self.val, "col_index")
			]}


class Gather(Node):
	def __init__(self, q, value_columns):
		self.q = q
		self.value_columns = value_columns

	def get_child(self): return self.q

	def eval(self, env):
		df = self.q.eval(env)
		value_vars = [df.columns[idx] for idx in self.value_columns]
		key_vars = [c for c in df.columns if c not in value_vars]
		return pd.melt(df, id_vars=key_vars, value_vars=value_vars, 
						var_name="KEY", value_name="VALUE")

	def to_dict(self):
		return {
			"type": "node",
			"op": "gather",
			"args": [self.q.to_dict(), value_to_dict(self.value_columns, "col_index_list")]
		}


class GatherNeg(Node):
	def __init__(self, q, key_columns):
		self.q = q
		self.key_columns = key_columns

	def eval(self, env):
		df = self.q.eval(env)
		key_vars = [df.columns[idx] for idx in self.key_columns]
		value_vars = [c for c in df.columns if c not in key_vars]
		return pd.melt(df, id_vars=key_vars, value_vars=value_vars, 
						var_name="KEY", value_name="VALUE")

	def to_dict(self):
		return {
			"type": "node",
			"op": "gather_neg",
			"args": [
				self.q.to_dict(), 
				value_to_dict(self.key_columns, "col_index_list"),
			]}


class GroupSummary(Node):
	def __init__(self, q, group_cols, aggr_col, aggr_func):
		self.q = q
		self.group_cols = group_cols
		self.aggr_col = aggr_col
		self.aggr_func = aggr_func

	def eval(self, env):
		df = self.q.eval(env)
		group_keys = [df.columns[idx] for idx in self.group_cols]
		target = df.columns[self.aggr_col]
		return df.groupby(group_keys)[target].agg(self.aggr_func).reset_index()

	def to_dict(self):
		return {
			"type": "node",
			"op": "group_sum",
			"args": [
				self.q.to_dict(), 
				value_to_dict(self.group_cols, "col_index_list"),
				value_to_dict(self.aggr_col, "col_index"), 
				value_to_dict(self.aggr_func, "aggr_func")
			]}


class CumSum(Node):
	def __init__(self, q, target):
		self.q = q
		self.target = target

	def eval(self, env):
		df = self.q.eval(env)
		ret = df.copy()
		ret["cumsum"] = ret[ret.columns[self.target]].cumsum()
		return ret

	def to_dict(self):
		return {
			"type": "node",
			"op": "cumsum",
			"args": [self.q.to_dict(), value_to_dict(self.target, "col_index")]
		}


class Mutate(Node):
	def __init__(self, q, col1, op, col2):
		self.q = q
		self.col1 = col1
		self.op = op
		self.col2 = col2

	def eval(self, env):
		assert (op in ["-", "+"])
		df = self.q.eval(env)
		ret = df.copy()
		new_col = get_fresh_col(list(ret.columns))[0]
		c1, c2 = ret.columns[self.col1], ret.columns[self.col2]
		if self.op == "+":
			ret[new_col] = (ret[c1] + ret[c2])
		elif self.op == "-":
			ret[new_col] = (ret[c1] - ret[c2])
		else:
			print("[ERROR] encounter wrong operator {} in Mutate".format(self.op))
			sys.exit(-1)
		#ret = ret.drop(columns=[c1, c2])
		return ret

	def to_dict(self):
		return {
			"type": "node",
			"op": "mutate",
			"args": [
				self.q.to_dict(), 
				value_to_dict(self.col1, "col_index"), 
				value_to_dict(self.op, "binop"), 
				value_to_dict(self.col2, "col_index")
			]}


class MutateCustom(Node):
	def __init__(self, q, col, op, const):
		self.q = q
		self.col = col
		self.op = op
		self.const = const

	def eval(self, env):
		assert(op == "==")
		df = self.q.eval(env)
		ret = df.copy()
		new_col = get_fresh_col(list(ret.columns))[0]
		c = ret.columns[self.col]
		if self.op != "==":
			print("[ERROR] encounter wrong operator {} in Mutate".format(self.op))
			sys.exit(-1)
		ret[new_col] = ret[c] == self.const
		#ret = ret.drop(columns=[c1, c2])
		return ret

	def to_dict(self):
		return {
			"type": "node",
			"op": "mutate_custom",
			"args": [
				self.q.to_dict(), 
				value_to_dict(self.col, "col_index"), 
				value_to_dict(self.op, "binop"), 
				value_to_dict(self.const, "constant")
			]}
