import pandas as pd
import numpy as np

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

class Table(object):
	def __init__(self, df):
		self.df = df

	@staticmethod
	def from_dict(json_data):
		return Table(pd.DataFrame.from_dict(json_data))

	def eval(self):
		return self.df

	def to_stmts(self, used_vars=[]):
		return [{"lhs": get_temp_var(used_vars), "rhs": {"op": "", "args": ["$input"]}}]

class Select(object):
	def __init__(self, q, cols):
		self.q = q
		self.cols = cols

	def eval(self):
		df = self.q.eval()
		return df[[df.columns[i] for i in self.cols]]

	def to_stmts(self, used_vars=[]):
		var = get_temp_var(used_vars)
		lines = self.q.to_stmts(used_vars + [var])
		child = lines[-1]
		return lines + [{"lhs": var,
				"rhs": {"op": "select", "args": [child["lhs"], [f"c{idx}" for idx in self.cols]]}}]


class Unite(object):
	def __init__(self, q, col1, col2):
		""" col1, col2 are column indexes"""
		self.q = q
		self.col1 = col1
		self.col2 = col2

	def eval(self):
		df = self.q.eval()
		ret = df.copy()
		new_col = get_fresh_col(list(ret.columns))[0]
		c1, c2 = ret.columns[self.col1], ret.columns[self.col2]
		ret[new_col] = ret[c1] + "_" + ret[c2]
		ret = ret.drop(columns=[c1, c2])
		return ret

	def to_stmts(self, used_vars=[]):
		var = get_temp_var(used_vars)
		lines = self.q.to_stmts(used_vars + [var])
		child = lines[-1]
		return lines + [
				{"lhs": var,
				"rhs": {"op": "unite", 
						"args": [child["lhs"], f"c{self.col1}", f"c{self.col1}"]}}]

class Filter(object):
	def __init__(self, q, col_index, op, const):
		self.q = q
		self.col_index = col_index
		self.op = op
		self.const = const

	def eval(self):
		df = self.q.eval()
		col = df.columns[self.col_index]
		if self.op == "==":
			return df[df[col] == self.const].reset_index()
		elif self.op == "!=":
			return df[df[col] != self.const].reset_index()
		else:
			sys.exit(-1)

	def to_stmts(self, used_vars=[]):
		var = get_temp_var(used_vars)
		lines = self.q.to_stmts(used_vars + [var])
		child = lines[-1]
		return lines + [
				{"lhs": var,
				 "rhs": {"op": "filter", 
						"args": [child["lhs"], f"c{self.col_index}", self.op, f'"{self.const}"']}}]

class Separate(object):
	def __init__(self, q, col_index):
		self.q = q
		self.col_index = col_index

	def eval(self):
		df = self.q.eval()
		ret = df.copy()
		col = ret.columns[self.col_index]
		splitted = ret[col].str.split(r"\s|_", n=1, expand=True)
		new_col_names = get_fresh_col(list(ret.columns), n=2)
		ret[new_col_names[0]] = splitted[0]
		ret[new_col_names[1]] = splitted[1]
		ret = ret.drop(columns=[col])
		return ret

	def to_stmts(self, used_vars=[]):
		var = get_temp_var(used_vars)
		lines = self.q.to_stmts(used_vars + [var])
		child = lines[-1]
		return lines + [
				{"lhs": var,
				 "rhs": {"op": "separate", 
						"args": [child["lhs"], f"c{self.col_index}"]}}]

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

class Spread(object):
	def __init__(self, q, key, val):
		self.q = q
		self.key = key
		self.val = val
	
	def eval(self):
		df = self.q.eval()
		key_col, val_col = df.columns[self.key], df.columns[self.val]
		index_cols = [c for c in list(df.columns) if c not in [key_col, val_col]]
		ret = df.set_index(index_cols)
		ret = multiindex_pivot(ret, columns=key_col, values=val_col).reset_index()
		return ret

	def to_stmts(self, used_vars=[]):
		var = get_temp_var(used_vars)
		lines = self.q.to_stmts(used_vars + [var])
		child = lines[-1]
		return lines + [
				{"lhs": var,
				 "rhs": {"op": "spread", 
						"args": [child["lhs"], f"c{self.key}", f"c{self.val}"]}}]

class Gather(object):
	def __init__(self, q, value_columns):
		self.q = q
		self.value_columns = value_columns

	def eval(self):
		df = self.q.eval()
		value_vars = [df.columns[idx] for idx in self.value_columns]
		key_vars = [c for c in df.columns if c not in value_vars]
		return pd.melt(df, id_vars=key_vars, value_vars=value_vars, 
						var_name="KEY", value_name="VALUE")

	def to_stmts(self, used_vars=[]):
		var = get_temp_var(used_vars)
		lines = self.q.to_stmts(used_vars + [var])
		child = lines[-1]
		return lines + [
				{"lhs": var,
				 "rhs": {"op": "gather", 
						"args": [child["lhs"], [f"c{idx}" for idx in self.value_columns]]}}]

class GatherNeg(object):
	def __init__(self, q, key_columns):
		self.q = q
		self.key_columns = key_columns

	def eval(self):
		df = self.q.eval()
		key_vars = [df.columns[idx] for idx in self.key_columns]
		value_vars = [c for c in df.columns if c not in key_vars]
		return pd.melt(df, id_vars=key_vars, value_vars=value_vars, 
						var_name="KEY", value_name="VALUE")

	def to_stmts(self, used_vars=[]):
		var = get_temp_var(used_vars)
		lines = self.q.to_stmts(used_vars + [var])
		child = lines[-1]
		return lines + [
				{"lhs": var,
				 "rhs": {"op": "gather", 
						"args": [child["lhs"], [f"c{idx}" for idx in self.key_columns]]}}]

class GroupSummary(object):
	def __init__(self, q, group_cols, aggr_col, aggr_func):
		self.q = q
		self.group_cols = group_cols
		self.aggr_col = aggr_col
		self.aggr_func = aggr_func

	def eval(self):
		df = self.q.eval()
		group_keys = [df.columns[idx] for idx in self.group_cols]
		target = df.columns[self.aggr_col]
		return df.groupby(group_keys)[target].agg(self.aggr_func).reset_index()

	def to_stmts(self, used_vars=[]):
		var = get_temp_var(used_vars)
		lines = self.q.to_stmts(used_vars + [var])
		child = lines[-1]
		return lines + [
				{"lhs": var,
				 "rhs": {"op": "group_sum", 
						"args": [child["lhs"], 
								 [f"c{idx}" for idx in self.group_cols], 
								 f"c{self.aggr_col}", 
								 self.aggr_func]}}]

class CumSum(object):
	def __init__(self, q, target):
		self.q = q
		self.target = target

	def eval(self):
		df = self.q.eval()
		ret = df.copy()
		ret["cumsum"] = ret[ret.columns[self.target]].cumsum()
		return ret

	def to_stmts(self, used_vars=[]):
		var = get_temp_var(used_vars)
		lines = self.q.to_stmts(used_vars + [var])
		child = lines[-1]
		return lines + [
				{"lhs": var,
				 "rhs": {"op": "group_sum", 
						"args": [child["lhs"], 
								 f"c{self.target}"]}}]

class Mutate(object):
	def __init__(self, q, col1, op, col2):
		assert (op in ["-", "+"])
		self.q = q
		self.col1 = col1
		self.op = op
		self.col2 = col2

	def eval(self):
		df = self.q.eval()
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

	def to_stmts(self, used_vars=[]):
		var = get_temp_var(used_vars)
		lines = self.q.to_stmts(used_vars + [var])
		child = lines[-1]
		return lines + [
				{"lhs": var,
				 "rhs": {"op": "group_sum", 
						"args": [child["lhs"], 
								 f"c{self.col1}", 
								 self.op,
								 f"c{self.col2}"]}}]

class MutateCustom(object):
	def __init__(self, q, col, op, const):
		assert(op == "==")
		self.q = q
		self.col = col
		self.op = op
		self.const = const

	def eval(self):
		df = self.q.eval()
		ret = df.copy()
		new_col = get_fresh_col(list(ret.columns))[0]
		c = ret.columns[self.col]
		if self.op != "==":
			print("[ERROR] encounter wrong operator {} in Mutate".format(self.op))
			sys.exit(-1)
		ret[new_col] = ret[c] == self.const
		#ret = ret.drop(columns=[c1, c2])
		return ret

	def to_stmts(self, used_vars=[]):
		var = get_temp_var(used_vars)
		lines = self.q.to_stmts(used_vars + [var])
		child = lines[-1]
		return lines + [
				{"lhs": var,
				 "rhs": {"op": "group_sum", 
						 "args": [child["lhs"], 
								  f"c{self.col}", 
								  self.op,
								  f'"{self.const}"']}}]

def statements_to_string(stmts):
	"""generate a string from stmts """
	result = []
	for s in stmts:
		lhs = s['lhs']
		f = s['rhs']['op']
		arg_str = ', '.join(['(' + ','.join(x) + ')' if isinstance(x,(list,tuple,)) 
					else x for x in s['rhs']['args']])
		result.append(f"{lhs} <- {f}({arg_str})")
	return result

	