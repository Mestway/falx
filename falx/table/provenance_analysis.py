import pandas as pd
import sys

# predicate language definition

class PredTrue(object):
	def __init__(self):
		pass

	def check(self, row):
		return True

	def print_str(self, indent="", multi_line=True):
		return f"{indent}True()"

class PredDisj(object):
	def __init__(self, preds):
		self.preds = preds		

	def check(self, row):
		return any([p.check(row) for p in self.preds])

	def print_str(self, indent="", multi_line=True):

		if multi_line == False:
			return f"Disjunction[ " + ", ".join([p.print_str("", False) for p in self.preds])  + " ]"


		out = f"{indent}Disjunction" + "\n"
		for p in self.preds:
			out += f"  {indent}{p.print_str(indent + '  ', multi_line)}\n"
		return out[:-1]

class PredConj(object):
	def __init__(self, preds):
		self.preds = preds

	def check(self, row):
		return all([p.check(row) for p in self.preds])

	def print_str(self, indent="", multi_line=True):
		out = f"{indent if multi_line else ''}Conjunction[ " + ", ".join([p.print_str("", False) for p in self.preds])  + " ]"

		return out

class PredContainsSubstr(object):
	"""check if there exists any value in the row contains the substring"""
	def __init__(self, val):
		self.val = val

	def check(self, row):
		return any([(self.val in v) for v in row if isinstance(v, str)])

	def print_str(self, indent="", multi_line=True):
		return f"{indent}substr({self.val})"

class PredContainsVal(object):
	def __init__(self, val):
		self.val = val

	def check(self, row):
		return self.val in row or any([str(self.val) == str(v) for v in row])

	def print_str(self, indent="", multi_line=True):
		return f"{indent}{self.val}"

# analysis functions

def provenance_analysis(node, output, inputs):
	"""Given the dict represented program, and the output table dataframe
		analyze components in the input that is related to outputs
	Args:
		node: a dictionary represented data structure
		output: the output data, represented as records dictionary (or a pandas dataframe)
		inputs: the list of input table, represented as input tuples
	"""

	# convert it into a dataframe
	if isinstance(output, pd.DataFrame):
		out_records = output.to_dict(orient="records")
	else:
		out_records = output
	
	current_exp = PredDisj([(PredConj([PredContainsVal(val) for key, val in r.items()])) for r in out_records])

	#print(current_exp.print_str())

	current_node = node
	while current_node["op"] != "table_ref":
		current_exp = provenance_analysis_one_step(current_node["op"], current_exp, inputs)
		current_node = current_node["children"][0]

	#print("==>")
	#print(current_exp.print_str())

	trimmed_inputs = [[r for r in input_records if current_exp.check([r[x] for x in r])] for input_records in inputs]

	return current_exp, trimmed_inputs


def provenance_analysis_one_step(op, pred, inputs):
	""" perform one_step backward provenance analysis"""

	if op == "select":
		return pred

	if op == "unite":
		if isinstance(pred, PredConj) or isinstance(pred, PredDisj):
			return pred.__class__([provenance_analysis_one_step(op, p, inputs) for p in pred.preds])
		if isinstance(pred, PredContainsVal) or isinstance(pred, PredContainsSubstr):
			if isinstance(pred.val, str) and ("_" in pred.val):
				splitted = pred.val.split("_")
				return PredDisj([PredContainsVal(pred.val), PredConj([ pred.__class__(s) for s in splitted])])
			else:
				return pred

	if op == "filter":
		return pred

	if op == "separate":
		if isinstance(pred, PredConj) or isinstance(pred, PredDisj):
			return pred.__class__([provenance_analysis_one_step(op, p, inputs) for p in pred.preds])
		if isinstance(pred, PredContainsVal):
			if isinstance(pred.val, str):
				return PredContainsSubstr(pred.val)
			else:
				return pred
		if isinstance(pred, PredContainsSubstr):
			return pred

	if op == "spread":
		if isinstance(pred, PredConj) or isinstance(pred, PredDisj):
			return PredDisj([provenance_analysis_one_step(op, p, inputs) for p in pred.preds])
		if isinstance(pred, PredContainsVal):
			return pred
		if isinstance(pred, PredContainsSubstr):
			return pred

	if op == "gather":

		headers = list(set([k for t in inputs for k in t[0].keys()]))

		if isinstance(pred, PredConj) or isinstance(pred, PredDisj):
			return pred.__class__([provenance_analysis_one_step(op, p, inputs) for p in pred.preds])
		if isinstance(pred, PredContainsVal):
			if str(pred.val) in headers:
				return PredTrue()
			else:
				return pred
		if isinstance(pred, PredContainsSubstr):
			if any([ pred.val in h for h in headers ]):
				return PredTrue()
			else:
				return pred

	if op in ["mutate", "mutate_custom", "cumsum", "group_sum"]:
		if isinstance(pred, PredConj) or isinstance(pred, PredDisj):
			return pred.__class__([provenance_analysis_one_step(op, p, inputs) for p in pred.preds])
		if isinstance(pred, PredContainsVal) or isinstance(pred, PredContainsSubstr):
			if isinstance(pred.val, str):
				return pred
			else:
				# number could be a derived value
				return PredTrue()

	if isinstance(pred, PredTrue):
		return PredTrue()
from falx.table.language import *

if __name__ == '__main__':
	print("===")
	q = Table(data_id=0)
	q = Gather(q, [1, 2])

	node = q.to_dict()
	print(q.stmt_string())

	inputs = [[
		{ "Bucket": "Bucket E", "Budgeted": 100, "Actual": 115 },
		{ "Bucket": "Bucket D", "Budgeted": 100, "Actual": 90 },
		{ "Bucket": "Bucket C", "Budgeted": 125, "Actual": 115 },
		{ "Bucket": "Bucket B", "Budgeted": 125, "Actual": 140 },
		{ "Bucket": "Bucket A", "Budgeted": 140, "Actual": 150 }
	]]

	output = [
		{'c_x': 'Actual', 'c_y': 115.0, 'c_column': 'Bucket E', 'c_color': 'Actual'}, 
		{'c_x': 'Actual', 'c_y': 90.0, 'c_column': 'Bucket D', 'c_color': 'Actual'}, 
		{'c_x': 'Budgeted', 'c_y': 100.0, 'c_column': 'Bucket D', 'c_color': 'Budgeted'}
	]

	out_df = pd.DataFrame.from_dict(output)

	pred, trimmed_inputs = provenance_analysis(node, out_df, inputs)

	print(pred.print_str())
	print(pd.DataFrame(trimmed_inputs[0]))