import pandas as pd

from falx.table.language import *
from falx.utils.synth_utils import remove_duplicate_columns, check_table_inclusion

def backward_eval(node, out_df, is_outer_most=True):
	"""Given an ast node, and the output dataframe, 
		find all possible premise chains branching out from the current dataframe
	Args:
		node: an ast node (generated from to_dict() method from operators in table.language)
		out_df: the output data_frame that should be included by the given input
		is_outer_most: whether the current node is the outermost level node
	Returns:
		a list of premise chains, prepsenting all possible premises that could lead to the current requirement
		each promise is in the form
			[(df1, path1), ..., (df_k, path_k), ...]
		it represents that the output of node at path_k should satisfy the premise that output includes df_k
		The premise chain starts with the current node
	"""

	#this is the premise to the current node:
	# we require that the output of the current node includes out_df (path is empty because we need no routing)
	current_premise = (out_df, [])

	all_premesis_chains = []
	if node["op"] != "table_ref":
		# evaluate all possible premise the direct child node
		inp_df_list = backward_eval_one_step(node["op"], out_df, is_outer_most)
		for inp_df in inp_df_list:
			# recursively calculate all premises from children
			all_premesis_chains_from_child = backward_eval(node["children"][0], inp_df, False)
			for premise_chain in all_premesis_chains_from_child:
				# also include the premise from the current node 
				# so that we get all premise chains starting from the current node
				combined_with_current = [current_premise]
				# updated paths from children by including the path to children
				for premise in premise_chain:
					combined_with_current += [(premise[0], [0] + premise[1])]
				all_premesis_chains.append(combined_with_current)
	else:
		# no children from the node
		all_premesis_chains.append([current_premise])
	
	return all_premesis_chains


def backward_eval_one_step(op, out_df, is_outer_most=False):
	"""backwardly evaluate an operator to infer property of the input
		Given the operator and the output dataframe, 
	Args:
		op: the operator
		out_df: the output data_frame requirement
	Retursn:
		all requirements for child nodes
	"""

	# get coumn names and schema of the out_df
	cols = out_df.columns
	schema = extract_table_schema(out_df)

	if op == "select":
		return [out_df]

	if op == "unite":
		candidates = []

		if not is_outer_most:
			# if the united column is removed
			# (it doesn't make sense to have both separate columns projected away 
			#  for the outermost level, otherwise unite is non-sense)
			candidates += [out_df]

		# if the united column is in the output
		for i, c in enumerate(out_df.columns):
			if schema[i] != "string":
				continue
			col_vals = out_df[c].to_list()

			if all(["_" in v for v in col_vals]):
				#out_df[[x for x in out_df.columns if x != c]]
				if not out_df.empty:
					t = Separate(Table(0), i).eval([out_df])
					candidates += [t]
				else:
					candidates += [out_df]
		return candidates

	if op == "filter":
		return [out_df]

	if op == "separate":
		# enumerate candidate key-value columns
		candidates = []

		if not is_outer_most:
			# if both of the separated columns are removed in projection
			# we only consider this if it is not in the outer_most level
			# (it doesn't make sense to have both separate columns projected away)
			candidates += [out_df]

		# if only one of the separated columns is in the output
		for i, sep_col in enumerate(cols):
			if schema[i] != "string":
				continue
			t = out_df[[c for c in cols if c != sep_col]]
			candidates.append(t)

		# if both of the separated columns are in the output
		for sep_col_indexes in itertools.combinations(range(len(cols)), 2):
			if not all([schema[i] == "string" for i in sep_col_indexes]):
				continue
			sep_cols = [cols[i] for i in sep_col_indexes]

			for sep in ["-", "_", " "]:
				t = Unite(Table(0), sep_col_indexes[0], sep_col_indexes[1], sep).eval([out_df])
				candidates.append(t)
			for sep in ["-", "_", " "]:
				t = Unite(Table(0), sep_col_indexes[1], sep_col_indexes[0], sep).eval([out_df])
				candidates.append(t)

		return candidates

	if op == "spread":
		candidates = []

		# case 1: the id column is gone
		if len(set(schema)) == 1:
			t = pd.melt(out_df, id_vars=[], value_vars=cols, var_name='varNameColumn')
			t = t[[c for c in t.columns if c != "varNameColumn"]]
			candidates += [t]

		# case 2: the id column is there, enumerate all possible id columns
		for i, id_col in enumerate(cols):

			if len(set([ty for k, ty in enumerate(schema) if k != i])) > 1:
				# the value columns have mixed datatype
				continue

			t = pd.melt(out_df, id_vars=[id_col], 
						value_vars=[c for c in cols if c != id_col],
						var_name='varNameColumn')
			t = t[[c for c in t.columns if c != "varNameColumn"]]
			candidates += [t]

		# case 3: id column is not just one
		for id_col_indexes in itertools.combinations(range(len(cols)), 2):
			 
			if len(set([ty for k, ty in enumerate(schema) if k not in id_col_indexes])) > 1:
				# the value columns have mixed datatype
				continue

			id_cols = [cols[k] for k in id_col_indexes]

			t = pd.melt(out_df, id_vars=id_cols, 
						value_vars=[c for c in cols if c not in id_cols],
						var_name='varNameColumn')
			t = t[[c for c in t.columns if c != "varNameColumn"]]
			candidates += [t]

		return candidates

	if op in ["gather", "gather_neg"]:
		candidates = []

		if not is_outer_most:
			# (it doesn't make sense to have both the key val column removed)
			candidates += [out_df]

		# if both of the separated columns are in the output
		for key_val in itertools.combinations(cols, 2):
			t = out_df[[c for c in cols if c not in key_val]]
			t = t.drop_duplicates()
			candidates += [t]

		return candidates

	if op in ["mutate", "mutate_custom", "cumsum", "group_sum"]:

		candidates = []
		if not is_outer_most:
			# if both of the separated columns are removed in projection
			# we only consider this if it is not in the outer_most level
			# (it doesn't make sense to have the generated column removed)
			candidates += [out_df]

		potential_new_col = []
		if op in ["mutate", "cumsum", "group_sum"]:
			potential_new_col = [c for i, c in enumerate(cols) if schema[i] == "number"]
		elif op == "mutate_custom":
			potential_new_col = [c for i, c in enumerate(cols) if schema[i] == "boolean"]

		for new_col in potential_new_col:
			t = out_df[[c for c in cols if c != new_col]]
			candidates += [t]

		return candidates

if __name__ == '__main__':

	inputs = [[
		{ "Bucket": "Bucket_E", "Budgeted": 100, "Actual": 115 },
		{ "Bucket": "Bucket_D", "Budgeted": 100, "Actual": 90 },
		{ "Bucket": "Bucket_C", "Budgeted": 125, "Actual": 115 },
		{ "Bucket": "Bucket_B", "Budgeted": 125, "Actual": 140 },
		{ "Bucket": "Bucket_A", "Budgeted": 140, "Actual": 150 }
	]]

	output = [
		{ "x": "Actual", "y": 115,  "color": "Actual", "column": "Bucket_E"},
		{ "x": "Actual", "y": 90,"color": "Actual", "column": "Bucket_D"},
		{ "x": "Budgeted","y": 100,  "color": "Budgeted", "column": "Bucket_D"},
	]

	out_df = pd.DataFrame.from_dict(output)

	out_df = remove_duplicate_columns(out_df)
	print(out_df)

	for df in backward_eval_one_step("gather", out_df, is_outer_most=True):
		print('-')
		print(df)
		print(check_table_inclusion(df.to_dict(orient="records"), inputs[0], wild_card=UNKNOWN))
