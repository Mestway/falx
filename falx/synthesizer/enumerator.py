import sys
import traceback
import copy
from pprint import pprint
import pandas as pd

from falx.synthesizer.table_lang import (Node, Table, Select, Unite, Filter, Separate, Spread, 
	Gather, GatherNeg, GroupSummary, CumSum, Mutate, MutateCustom)
from falx.synthesizer.utils import HOLE
from falx.synthesizer import enum_strategies 

abstract_combinators = {
	"Select": lambda q: Select(q, cols=HOLE),
	"Unite": lambda q: Unite(q, col1=HOLE, col2=HOLE),
	"Filter": lambda q: Filter(q, col_index=HOLE, op=HOLE, const=HOLE),
	"Separate": lambda q: Separate(q, col_index=HOLE),
	"Spread": lambda q: Spread(q, key=HOLE, val=HOLE),
	"Gather": lambda q: Gather(q, value_columns=HOLE),
	"GatherNeg": lambda q: GatherNeg(q, key_columns=HOLE),
	"GroupSummary": lambda q: GroupSummary(q, group_cols=HOLE, aggr_col=HOLE, aggr_func=HOLE),
	"CumSum": lambda q: CumSum(q, target=HOLE),
	"Mutate": lambda q: Mutate(q, col1=HOLE, op=HOLE, col2=HOLE),
	"MutateCustom": lambda q: MutateCustom(q, col=HOLE, op=HOLE, const=HOLE), 
}

def update_tree_value(node, path, new_val):
	"""from a given ast node, locate the refence to the arg"""
	for k in path:
		node = node["children"][k]
	node["value"] = new_val

def get_node(node, path):
	for k in path:
		node = node["children"][k]
	return node

class Sythesizer(object):

	def __init__(self):
		self.config = {
			"filer_op": [">", "<", "=="],
			"constants": [],
			"aggr_func": ["mean", "sum", "count"],
			"mutate_op": ["+", "-"]
		}

	def enum_sketches(self, size, num_inputs):
		"""enumerate program sketches up to the given size"""
		candidates = {}
		for level in range(0, size + 1):
			candidates[level] = []
			if level == 0:
				candidates[level] += [Table(data_id=i) for i in range(num_inputs)]
			else:
				for p in candidates[level - 1]:
					for op in abstract_combinators:
						q = abstract_combinators[op](copy.copy(p))
						if not enum_strategies.disable_sketch(q):
							candidates[level].append(q)
		return candidates


	def pick_var(self, ast, inputs):
		"""Given a partial program and input tables, decide next vars to instantiate"""

		def get_paths_to_all_holes(node):
			results = []
			for i, child in enumerate(node["children"]):
				if child["type"] == "node":
					# try to find a variable to infer
					paths = get_paths_to_all_holes(child)
					for path in paths:
						results.append([i] + path)
				elif child["value"] == HOLE:
					# we find a variable to infer
					results.append([i])
			return results

		paths_to_holes = get_paths_to_all_holes(ast)

		if len(paths_to_holes) > 0:
			path = paths_to_holes[0]
			return path, Node.load_from_dict(get_node(ast, path[:-1])).infer_domain(arg_id=path[-1], inputs=inputs, config=self.config)
		else:
			return None, None

	def instantiate(self, p, inputs):
		"""instantiate one hole in the program sketch"""
		ast = p.to_dict()
		path, domain = self.pick_var(ast, inputs)
		#print(domain)
		if path is None:
			return []
		candidates = []
		for val in domain:
			new_ast = copy.deepcopy(ast)
			update_tree_value(new_ast, path, val)
			candidates.append(Node.load_from_dict(new_ast))
		return candidates

	def iteratively_instantiate_and_print(self, p, inputs, level):
		"""iteratively instantiate a program (for the purpose of debugging)"""
		print(f"{'  '.join(['' for _ in range(level)])}{p.stmt_string()}")
		results = []
		if p.is_abstract():
			candidates = self.instantiate(p, inputs)
			for c in candidates:
				results += self.iteratively_instantiate_and_print(c, inputs, level + 1)
			return results
		else:
			return [p]

	def enumerative_synthesis(self, inputs, output):
		all_sketches = self.enum_sketches(size=3, num_inputs=len(inputs))
		concrete_programs = []
		for level, sketches in all_sketches.items():
			for s in sketches:
				concrete_programs += self.iteratively_instantiate_and_print(s, inputs, 1)
		for p in concrete_programs:
			print(p.stmt_string())
			try:
				print(p.eval(inputs))
			except Exception as e:
				print(f"[error] {sys.exc_info()[0]} {e}")
				tb = sys.exc_info()[2]
				tb_info = ''.join(traceback.format_tb(tb))
				print(tb_info)
		print("----")
		print(f"number of programs: {len(concrete_programs)}")

		# ast = p.to_dict()
		# print(p.stmt_string())
		# if not p.is_abstract():
		# 	continue
		# candidates = self.instantiate(p, inputs)
		# for c in candidates:
		# 	print("  {}".format(c.stmt_string()))

if __name__ == '__main__':

	inputs = [[
		{ "Bucket": "Bucket E", "Budgeted": 100, "Actual": 115 },
		{ "Bucket": "Bucket D", "Budgeted": 100, "Actual": 90 },
		{ "Bucket": "Bucket C", "Budgeted": 125, "Actual": 115 },
		{ "Bucket": "Bucket B", "Budgeted": 125, "Actual": 140 },
		{ "Bucket": "Bucket A", "Budgeted": 140, "Actual": 150 }
	]]

	output = [
		{ "x": "Actual", "y": 115,  "color": "Actual", "column": "Bucket E"},
		{ "x": "Actual", "y": 90,"color": "Actual", "column": "Bucket D"},
		{ "x": "Budgeted","y": 100,  "color": "Budgeted", "column": "Bucket D"},
	]
	Sythesizer().enumerative_synthesis([pd.DataFrame.from_dict(t) for t in inputs], output)