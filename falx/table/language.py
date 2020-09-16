import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
import copy
import itertools


# two special symbols used in the language
HOLE = "_?_"
UNKNOWN = "_UNK_"

# restrict how many keys can be generated from spread
SPREAD_MAX_KEYSIZE = 10

class Node(ABC):
	def __init__(self):
		super(AbstractExpression, self).__init__()

	@abstractmethod
	def eval(self, inputs):
		"""the inputs are dataframes,
			it returns a pandas dataframe representation"""
		pass

	@abstractmethod
	def to_dict(self):
		pass

	@abstractmethod
	def infer_domain(self, arg_id, config):
		pass

	@abstractmethod
	def infer_output_info(self, inputs):
		pass

	@staticmethod
	def load_from_dict(ast):
		"""given a dictionary represented AST, load it in to a program form"""
		constructors = {
			"select": Select, "unite": Unite,
			"filter": Filter, "separate": Separate,
			"spread": Spread, "gather": Gather,
			"group_sum": GroupSummary,
			"cumsum": CumSum, "mutate": Mutate,
			"mutate_custom": MutateCustom,
		}
		if ast["op"] == "table_ref":
			return Table(ast["children"][0]["value"])
		else:
			node = constructors[ast["op"]](
						Node.load_from_dict(ast["children"][0]), 
						*[arg["value"] for arg in ast["children"][1:]])
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
				for i, arg in enumerate(ast["children"]):
					# check if the argument is an ast 
					if isinstance(arg, (dict,)) and arg["type"] == "node":
						stmts, used_vars = _recursive_translate(ast["children"][0], used_vars)
						sub_tree_stmts += stmts
						# the subtree is replaced by a reference to the variable
						retvar = stmts[-1]["return_as"]
						stmt_dict["children"][i] = {"value": retvar, "type": "variable"}
				
				# use a temp variable to wrap the current statement, and add it to the coolection
				var = get_temp_var(used_vars)
				stmt_dict["return_as"] = var
				return sub_tree_stmts + [stmt_dict], used_vars + [var]

		stmts, _ = _recursive_translate(self.to_dict(), [])
		return stmts

	def is_abstract(self):
		"""Check if the subtree is abstract (contains any holes)"""
		def contains_hole(node):
			for i, arg in enumerate(node["children"]):
				if arg["type"] == "node":
					if contains_hole(arg):
						return True
				elif arg["value"] == HOLE:
					# we find a variable to infer
					return True
			return False
		return contains_hole(self.to_dict())
	
	def stmt_string(self):
		"""generate a string from stmts, for the purpose of pretty printing"""
		stmts = self.to_stmt_dict()
		result = []
		for s in stmts:
			lhs = s['return_as']
			f = s['op']
			arg_str = ', '.join([str(x['value']) for x in s["children"]])
			result.append(f"{lhs} <- {f}({arg_str})")

		return "; ".join(result)


class Table(Node):
	def __init__(self, data_id):
		self.data_id = data_id

	def infer_domain(self, arg_id, inputs, config):
		assert False, "Table has no args to infer domain."

	def infer_output_info(self, inputs):
		"""infer output schema """
		inp = inputs[self.data_id]
		if isinstance(inp, (list,)):
			df = pd.DataFrame.from_dict(inp)
		else:
			df = inp
		schema = extract_table_schema(df)
		return schema

	def eval(self, inputs):
		inp = inputs[self.data_id]
		if isinstance(inp, (list,)):
			df = pd.DataFrame.from_dict(inp)
		else:
			df = inp


		return df

	def to_dict(self):
		return {
			"type": "node",
			"op": "table_ref",
			"children": [
				value_to_dict(self.data_id, "table_id")
			]
		}


class Select(Node):
	def __init__(self, q, cols):
		self.q = q
		self.cols = cols

	def infer_domain(self, arg_id, inputs, config):
		if arg_id == 1:
			input_schema = self.q.infer_output_info(inputs)
			col_num = len(input_schema)
			col_list_candidates = []
			for size in range(1, col_num + 1):
				col_list_candidates += list(itertools.combinations(list(range(col_num)), size))
			return col_list_candidates
		else:
			assert False, "[Select] No args to infer domain for id > 1."

	def infer_output_info(self, inputs):
		schema = self.q.infer_output_info(inputs)
		return [s for i, s in enumerate(schema) if i in self.cols]

	def eval(self, inputs):
		df = self.q.eval(inputs)
		return df[[df.columns[i] for i in self.cols]]

	def backward_eval(self, output):
		# the input table should contain every value appear in the output table
		return [output]

	def to_dict(self):
		return {
			"type": "node",
			"op": "select",
			"children": [self.q.to_dict(), value_to_dict(self.cols, "col_index_list")]
		}


class Unite(Node):
	def __init__(self, q, col1, col2, sep="_"):
		""" col1, col2 are column indexes"""
		self.q = q
		self.col1 = col1
		self.col2 = col2
		self.sep = sep

	def infer_domain(self, arg_id, inputs, config):
		input_schema = self.q.infer_output_info(inputs)
		str_cols = [i for i, s in enumerate(input_schema) if s == "string"]
		if arg_id == 1:
			return str_cols
		if arg_id == 2:
			# refine the domain according to the first argumnet
			return str_cols if self.col1 == HOLE else [i for i in str_cols if i > self.col1]
		else:
			assert False, "[Unite] No args to infer domain for id > 2."

	def infer_output_info(self, inputs):
		input_schema = self.q.infer_output_info(inputs)
		return [s for i,s in enumerate(input_schema) if i not in [self.col1, self.col2]] + ["string"]

	def eval(self, inputs):
		df = self.q.eval(inputs)
		ret = df.copy()
		new_col = get_fresh_col(list(ret.columns))[0]
		c1, c2 = ret.columns[self.col1], ret.columns[self.col2]
		ret[new_col] = ret[c1] + self.sep + ret[c2]
		ret = ret.drop(columns=[c1, c2])
		return ret

	def backward_eval(self, output):
		# if could be the case that all column in the output 
		possible_premise = [output]
		cols = list(output[0].keys())
		return output

	def to_dict(self):
		return {
			"type": "node",
			"op": "unite",
			"children": [
				self.q.to_dict(), 
				value_to_dict(self.col1, "col_index"), 
				value_to_dict(self.col2, "col_index")]}


class Filter(Node):
	def __init__(self, q, col_index, op, const):
		self.q = q
		self.col_index = col_index
		self.op = op
		self.const = const

	def infer_domain(self, arg_id, inputs, config):
		if arg_id == 1:
			col_num = len(self.q.infer_output_info(inputs))
			return list(range(col_num))
		elif arg_id == 2:
			return config["filer_op"]
		elif arg_id == 3:
			return config["constants"]
		else:
			assert False, "[Filter] No args to infer domain for id > 3."

	def infer_output_info(self, inputs):
		return self.q.infer_output_info(inputs)

	def eval(self, inputs):
		df = self.q.eval(inputs)
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
			"children": [
				self.q.to_dict(), 
				value_to_dict(self.col_index, "col_index"), 
				value_to_dict(self.op, "binop"), 
				value_to_dict(self.const, "constant")
			]}


class Separate(Node):
	def __init__(self, q, col_index):
		self.q = q
		self.col_index = col_index

	def infer_domain(self, arg_id, inputs, config):
		if arg_id == 1:
			try:
				df = self.q.eval(inputs)
			except Exception as e:
				print(f"[eval error in infer_domain] {e}")
				return []
			input_schema = self.q.infer_output_info(inputs)
			domain = []
			#TODO: need to improve precisions of type inferene
			# print(df)
			# print(input_schema)
			for i, s in enumerate(input_schema):
				if s != "string": 
					continue
				l = list(df[df.columns[i]])
				separators = [" ", "-", "_"]
				contain_sep = False
				for sep in separators:
					if all([sep in str(x) for x in l]):
						contain_sep = True
						break
				if contain_sep:
					domain.append(i)
			return domain
		else:
			assert False, "[Separate] No args to infer domain for id > 1."

	def infer_output_info(self, inputs):
		input_schema = self.q.infer_output_info(inputs)
		return [s for i, s in enumerate(input_schema) if i != self.col_index] + ["string", "string"]

	def eval(self, inputs):
		df = self.q.eval(inputs)

		ret = df.copy()
		col = ret.columns[self.col_index]

		# enable splitting by "_", "-", and whitespace (but only split once)
		splitted = ret[col].str.split(r"\s|_|-", n=1, expand=True)
		new_col_names = get_fresh_col(list(ret.columns), n=2)
		ret[new_col_names[0]] = splitted[0]
		ret[new_col_names[1]] = splitted[1]
		ret = ret.drop(columns=[col])
		return ret

	def to_dict(self):
		return {
			"type": "node",
			"op": "separate",
			"children": [self.q.to_dict(), value_to_dict(self.col_index, "col_index")]
		}
		

class Spread(Node):
	def __init__(self, q, key, val):
		self.q = q
		self.key = key
		self.val = val

	def infer_domain(self, arg_id, inputs, config):
		schema = self.q.infer_output_info(inputs)
		if arg_id == 1:
			if self.q.is_abstract():
				return list(range(len(schema)))
			else:
				# approximation: only get fields with more than one values
				# for the purpose of avoiding empty fields
				try:
					df = self.q.eval(inputs)
				except Exception as e:
					print(f"[eval error in infer_domain] {e}")
					return []
				cols = []
				for i, c in enumerate(df.columns):					
					l = list(df[c])
					vals_cnt = [l.count(x) for x in set(l)]
					# (1) all values should have the same cardinality
					# (2) their cardinality should all be greater than 1
					# (3) there should be at least two distrint value
					if len(set(vals_cnt)) == 1 and vals_cnt[0] > 1 and vals_cnt[0] != len(l):
						cols.append(i)
				return cols
		if arg_id == 2:
			if self.key != HOLE:
				try:
					df = self.q.eval(inputs)
				except Exception as e:
					print(f"[eval error in infer_domain] {e}")
					return []

				val_col_domain = []
				for i, vcol in enumerate(df.columns):
					if i == self.key:
						continue

					# values in the key column
					key_values = list(df[df.columns[self.key]])
					key_cnt = [key_values.count(x) for x in set(key_values)]
					
					# values in the id column (columns outside of key or val)
					id_cols = [c for k, c in enumerate(df.columns) if k != i and k != self.key]
					id_value_tuples = [tuple(x) for x in df[id_cols].to_records(index=False)]

					# restrict how many keys can be maximally generated from spread
					if SPREAD_MAX_KEYSIZE != None and len(set(key_values)) > SPREAD_MAX_KEYSIZE:
						continue

					# print("...>>>>>>>>")
					# print(id_cols)
					# print(key_values)
					# print(set(key_values))
					# print(key_cnt)
					# print(set(id_value_tuples))
					# print("{} {} {}".format(len(set(id_value_tuples)), key_cnt[0], len(set(key_values))))

					# only add the value column into the domain 
					# if #cardinality of key column * #distinct values in id column matches the # of rows tables
					if len(set(id_value_tuples)) *  len(set(key_values)) == len(key_values):
						# if it contains duplicate entries, remove them
						id_key_content = df[id_cols + [df.columns[self.key]]]
						if not id_key_content.duplicated().any():
							val_col_domain.append(i)

				return val_col_domain #[i for i in range(len(schema)) if i != self.key]
			else:
				return list(range(len(schema)))
		else:
			assert False, "[Spread] No args to infer domain for id > 2."

	def infer_output_info(self, inputs):
		if self.is_abstract():
			return None
		else:
			try:
				schema = extract_table_schema(self.eval(inputs))
				return schema
			except Exception as e:
				#TODO: use this to indicate the domain would be empty
				print(f"[eval error in infer_domain] {e}")
				return []

	def eval(self, inputs):
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
		df = self.q.eval(inputs)
		key_col, val_col = df.columns[self.key], df.columns[self.val]
		index_cols = [c for c in list(df.columns) if c not in [key_col, val_col]]
		ret = df.set_index(index_cols)
		ret = multiindex_pivot(ret, columns=key_col, values=val_col).reset_index()
		return ret

	def to_dict(self):
		return {
			"type": "node",
			"op": "spread",
			"children": [
				self.q.to_dict(), 
				value_to_dict(self.key, "col_index"), 
				value_to_dict(self.val, "col_index")
			]}


class Gather(Node):
	def __init__(self, q, value_columns):
		self.q = q
		self.value_columns = value_columns

	def infer_domain(self, arg_id, inputs, config):

		if arg_id == 1:
			input_schema = self.q.infer_output_info(inputs)
			col_num = len(input_schema)
			col_list_candidates = []

			# at least leave one column as the key column
			# also, choose the maximum list size based on config if the list is too long
			# 	(this prevents exponential enumeration when the table is too wide)
			max_val_list_size = min(col_num - 1, config["gather_max_val_list_size"])

			fw_col_lists = []
			for size in range(2, max_val_list_size + 1):
				for l in list(itertools.combinations(list(range(col_num)), size)):
					# only consider these fields together if they have the same type
					if len(set([input_schema[i] for i in l])) == 1:
						fw_col_lists.append(l)

			## this is the gahter neg case: enumerate keys (instead of columns)
			# leave at least two columns as values columns that will be unpivoted
			# also don't exceed col_num - config["gather_max_val_list_size"] 
			#   (since such query is already covered in gather(..))
			# also don't exceed config["gather_max_key_list_size"] to prevent explosion
			max_key_list_size = min(col_num - 2, 
									col_num - config["gather_max_val_list_size"] - 1, 
									config["gather_max_key_list_size"])
			
			# only consider such gather_neg stype if the table size is greater than config["gather_max_key_list_size"]
			bw_col_lists = []
			if max_key_list_size > 0:			
				for size in range(1, max_key_list_size + 1):
					for l in list(itertools.combinations(list(range(col_num)), size)):
						# only consider these fields together if they have the same type
						if len(set([input_schema[i] for i in range(len(input_schema)) if i not in l])) == 1:
							bw_col_lists.append(tuple([x for x in range(col_num) if x not in l]))

			# col_list_candidates = [(1,2,3,4,5)]
			# print(col_list_candidates)
			col_list_candidates = []
			for i in range(max(len(fw_col_lists), len(bw_col_lists))):
				if i < len(bw_col_lists):
					col_list_candidates.append(bw_col_lists[i])
				if i < len(fw_col_lists):
					col_list_candidates.append(fw_col_lists[i])

			#col_list_candidates = [(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)]

			# # only consider consecutive columns
			# filtered = []
			# for lst in col_list_candidates:
			# 	is_consecutive = True
			# 	for i, v in enumerate(lst):
			# 		if lst[i] - lst[0] != i - 0:
			# 			is_consecutive = False
			# 	if is_consecutive == True:
			# 		filtered.append(lst)
			# col_list_candidates = filtered

			return col_list_candidates
		else:
			assert False, "[Gather] No args to infer domain for id > 1."

	def infer_output_info(self, inputs):
		input_schema = self.q.infer_output_info(inputs)

		gather_schema = list(set([input_schema[i] for i in self.value_columns]))

		val_field_type = "string"
		if len(gather_schema) == 1 and gather_schema[0] == "number":
			val_field_type = "number"

		return [s for i, s in enumerate(input_schema) if i not in self.value_columns] + ["string"] + [val_field_type]

	def eval(self, inputs):
		df = self.q.eval(inputs)
		value_vars = [df.columns[idx] for idx in self.value_columns]
		key_vars = [c for c in df.columns if c not in value_vars]
		return pd.melt(df, id_vars=key_vars, value_vars=value_vars, 
						var_name="KEY", value_name="VALUE")

	def to_dict(self):
		return {
			"type": "node",
			"op": "gather",
			"children": [self.q.to_dict(), value_to_dict(self.value_columns, "col_index_list")]
		}

class GroupSummary(Node):
	def __init__(self, q, group_cols, aggr_col, aggr_func):
		self.q = q
		self.group_cols = group_cols
		self.aggr_col = aggr_col
		self.aggr_func = aggr_func

	def infer_domain(self, arg_id, inputs, config):
		schema = self.q.infer_output_info(inputs)
		if arg_id == 1:
			# approximation: only get fields with more than one values
			# for the purpose of avoiding empty fields
			try:
				df = self.q.eval(inputs)
			except Exception as e:
				print(f"[eval error in infer_domain] {e}")
				return []

			# use this list to store primitive table keys, 
			# use them to elimiate column combinations that contain no duplicates
			table_keys = []

			col_num = len(schema)
			col_list_candidates = []
			for size in range(1, col_num + 1 - 1):
				for gb_keys in itertools.combinations(list(range(col_num)), size):
					if any([set(banned).issubset(set(gb_keys)) for banned in table_keys]):
						# current key group is subsumbed by a table key, so all fields will be distinct
						continue
					gb_cols = df[[df.columns[k] for k in gb_keys]]
					if not gb_cols.duplicated().any():
						# a key group is valid for aggregation 
						#   if there exists at least a key appear more than once
						table_keys.append(gb_keys)
						continue
		
					col_list_candidates += [gb_keys]
			return col_list_candidates
		elif arg_id == 2:
			number_fields = [i for i,s in enumerate(schema) if s == "number"]
			if self.group_cols != HOLE:
				cols = [i for i in number_fields if i not in self.group_cols]
			else:
				cols = number_fields
			# the special column -1 is used for the purpose of "count", no other real intent
			cols += [-1]
			return cols
		elif arg_id == 3:
			if self.aggr_col != HOLE:
				if self.aggr_col == -1:
					return ["count"] if "count" in config["aggr_func"] else []
				else:
					return [f for f in config["aggr_func"] if f != "count"]
			else:
				return config["aggr_func"]
		else:
			assert False, "[Gather] No args to infer domain for id > 1."

	def infer_output_info(self, inputs):
		input_schema = self.q.infer_output_info(inputs)
		aggr_type = input_schema[self.aggr_col] if self.aggr_func != "count" else "number"
		return [s for i, s in enumerate(input_schema) if i in self.group_cols] + [aggr_type]

	def eval(self, inputs):
		df = self.q.eval(inputs)
		group_keys = [df.columns[idx] for idx in self.group_cols]
		target = df.columns[self.aggr_col]
		res = df.groupby(group_keys).agg({target: self.aggr_func})
		if self.aggr_func == "mean":
			res[target] = res[target].round(2)
		res = res.rename(columns={target: f'{self.aggr_func}_{target}'}).reset_index()
		return res

	def to_dict(self):
		return {
			"type": "node",
			"op": "group_sum",
			"children": [
				self.q.to_dict(), 
				value_to_dict(self.group_cols, "col_index_list"),
				value_to_dict(self.aggr_col, "col_index"), 
				value_to_dict(self.aggr_func, "aggr_func")
			]}


class CumSum(Node):
	def __init__(self, q, target):
		self.q = q
		self.target = target

	def infer_domain(self, arg_id, inputs, config):
		if arg_id == 1:
			input_schema = self.q.infer_output_info(inputs)
			return [i for i, s in enumerate(input_schema) if s == "number"]
		else:
			assert False, "[CumSum] No args to infer domain for id > 1."

	def infer_output_info(self, inputs):
		input_schema = self.q.infer_output_info(inputs)

		return input_schema + ["number"]

	def eval(self, inputs):
		df = self.q.eval(inputs)
		ret = df.copy()
		#new_col = get_fresh_col(list(ret.columns))[0]
		ret["cumsum"] = ret[ret.columns[self.target]].cumsum()
		return ret

	def to_dict(self):
		return {
			"type": "node",
			"op": "cumsum",
			"children": [self.q.to_dict(), value_to_dict(self.target, "col_index")]
		}


class Mutate(Node):
	def __init__(self, q, col1, op, col2):
		self.q = q
		self.col1 = col1
		self.op = op
		self.col2 = col2

	def infer_domain(self, arg_id, inputs, config):
		if arg_id in [1, 3]:
			input_schema = self.q.infer_output_info(inputs)
			number_fields = [i for i, s in enumerate(input_schema) if s == "number"]
			if arg_id == 1:
				return number_fields
			elif arg_id == 3:
				if self.col1 != HOLE and self.op != HOLE:
					if self.op == "-":
						return [i for i in number_fields if i != self.col1]
					elif self.op == "+":
						return [i for i in number_fields if i >= self.col1]
				else:
					return number_fields
		elif arg_id == 2:
			return config["mutate_op"]
		else:
			assert False, "[Mutate] No args to infer domain for id > 3."

	def infer_output_info(self, inputs):
		input_schema = self.q.infer_output_info(inputs)
		return input_schema + ["number"]

	def eval(self, inputs):
		assert (self.op in ["-", "+"])
		df = self.q.eval(inputs)
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
			"children": [
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

	def infer_domain(self, arg_id, inputs, config):
		if arg_id == 1:
			input_schema = self.q.infer_output_info(inputs)
			return [i for i, s in enumerate(input_schema) if s == "number"]
		elif arg_id == 2:
			return config["mutate_op"]
		elif arg_id == 3:
			return config["constants"]
		else:
			assert False, "[MutateCustom] No args to infer domain for id > 3."

	def infer_output_info(self, inputs):
		input_schema = self.q.infer_output_info(inputs)
		return input_schema + ["number"]

	def eval(self, inputs):
		assert(op == "==")
		df = self.q.eval(inputs)
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
			"children": [
				self.q.to_dict(), 
				value_to_dict(self.col, "col_index"), 
				value_to_dict(self.op, "binop"), 
				value_to_dict(self.const, "constant")
			]}

#utility functions

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

def extract_table_schema(df):
	"""Given a dataframe, extract it's schema """
	def dtype_mapping(dtype):
		"""map pandas datatype to c """
		dtype = str(dtype)
		if dtype == "object" or dtype == "string":
			return "string"
		elif "int" in dtype or "float" in dtype:
			return "number"
		elif "bool" in dtype:
			return "bool"
		else:
			print(f"[unknown type] {dtype}")
			sys.exit(-1)

	schema = [dtype_mapping(s) for s in df.infer_objects().dtypes]
	return schema