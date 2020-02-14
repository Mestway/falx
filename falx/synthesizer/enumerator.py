import sys
import traceback
import copy
from pprint import pprint
import pandas as pd

from falx.synthesizer.table_lang import (Node, Table, Select, Unite, Filter, Separate, Spread, 
	Gather, GatherNeg, GroupSummary, CumSum, Mutate, MutateCustom)
from falx.synthesizer.utils import HOLE
from falx.synthesizer import enum_strategies 
from falx.synthesizer import abstract_eval
from falx.synth_utils import remove_duplicate_columns, check_table_inclusion

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

class Synthesizer(object):

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

	def pick_vars(self, ast, inputs):
		"""list paths to all holes in the given ast"""
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
		return get_paths_to_all_holes(ast)

	def infer_domain(self, ast, var_path, inputs):
		node = Node.load_from_dict(get_node(ast, var_path[:-1]))
		return node.infer_domain(arg_id=var_path[-1], inputs=inputs, config=self.config)

	def instantiate(self, ast, var_path, inputs):
		"""instantiate one hole in the program sketch"""
		domain = self.infer_domain(ast, var_path, inputs)
		candidates = []
		for val in domain:
			new_ast = copy.deepcopy(ast)
			update_tree_value(new_ast, var_path, val)
			candidates.append(new_ast)
		return candidates

	def instantiate_one_level(self, ast, inputs):
		"""generate program instantitated from the most recent level
			i.e., given an abstract program, it will enumerate all possible abstract programs that concretize
		"""
		var_paths = self.pick_vars(ast, inputs)

		# there is no variables to instantiate
		if var_paths == []:
			return [], []

		# find all variables at the innermost level
		innermost_level = max([len(p) for p in var_paths])
		target_vars = [p for p in var_paths if len(p) == innermost_level]

		recent_candidates = [ast]
		for var_path in target_vars:
			temp_candidates = []
			for partial_prog in recent_candidates:
				temp_candidates += self.instantiate(partial_prog, var_path, inputs)
			recent_candidates = temp_candidates

		# for c in recent_candidates:
		# 	nd = Node.load_from_dict(c)
		# 	print(f"{' | '}{nd.stmt_string()}")
		
		# this show how do we trace to the most recent program level
		concrete_program_level = innermost_level - 1

		return recent_candidates, concrete_program_level

	def iteratively_instantiate_and_print(self, p, inputs, level, print_programs=False):
		"""iteratively instantiate a program (for the purpose of debugging)"""
		if print_programs:
			print(f"{'  '.join(['' for _ in range(level)])}{p.stmt_string()}")
		results = []
		if p.is_abstract():
			ast = p.to_dict()
			var_path = self.pick_vars(ast, inputs)[0]
			#domain = self.infer_domain(ast, path, inputs)
			candidates = self.instantiate(ast, var_path, inputs)
			for c in candidates:
				nd = Node.load_from_dict(c)
				results += self.iteratively_instantiate_and_print(nd, inputs, level + 1, print_programs)
			return results
		else:
			return [p]
 
	def iteratively_instantiate_with_premise_check(self, p, inputs, premise_chain):
		"""iteratively instantiate abstract programs w/ promise check """

		def instantiate_with_premise_check(p, inputs, premise_chain):
			"""instantiate programs and then check each one of them against the premise """
			results = []
			if p.is_abstract():
				ast = p.to_dict()
				next_level_programs, level = self.instantiate_one_level(ast, inputs)
				for _ast in next_level_programs:
					# find premise corresponding to this level of program
					premise, subquery_path = [pm for pm in premise_chain if len(pm[1]) == level][0]
					
					# check if the subquery result contains the premise
					subquery_node = get_node(_ast, subquery_path)
					subquery_res = Node.load_from_dict(subquery_node).eval(inputs)
					if check_table_inclusion(premise.to_dict(orient="records"), subquery_res.to_dict(orient="records")):
						#print(f"{' - '}{Node.load_from_dict(_ast).stmt_string()}")
						results.append(Node.load_from_dict(_ast))
				return results
			else:
				return []
		results = []
		if p.is_abstract():
			candidates = instantiate_with_premise_check(p, inputs, premise_chain)
			for _p in candidates:
				results += self.iteratively_instantiate_with_premise_check(_p, inputs, premise_chain)
			return results
		else:
			return [p]

	def iteratively_instantiate_with_premises_check(self, p, inputs, premise_chains):
		"""iteratively instantiate abstract programs w/ promise check """

		def instantiate_with_premises_check(p, inputs, premise_chains):
			"""instantiate programs and then check each one of them against the premise """
			results = []
			if p.is_abstract():
				ast = p.to_dict()
				next_level_programs, level = self.instantiate_one_level(ast, inputs)
				for _ast in next_level_programs:

					premises_at_level = [[pm for pm in premise_chain if len(pm[1]) == level][0] for premise_chain in premise_chains]

					subquery_res = None
					for premise, subquery_path in premises_at_level:
						if subquery_res is None:
							# check if the subquery result contains the premise
							subquery_node = get_node(_ast, subquery_path)
							subquery_res = Node.load_from_dict(subquery_node).eval(inputs)
						
						if check_table_inclusion(premise.to_dict(orient="records"), subquery_res.to_dict(orient="records")):
							#print(f"{' - '}{Node.load_from_dict(_ast).stmt_string()}")
							results.append(Node.load_from_dict(_ast))
							break

				return results
			else:
				return []
		results = []
		if p.is_abstract():
			candidates = instantiate_with_premises_check(p, inputs, premise_chains)
			for _p in candidates:
				results += self.iteratively_instantiate_with_premises_check(_p, inputs, premise_chains)
			return results
		else:
			return [p]

	def enumerative_search(self, inputs, output, max_prog_size):
		"""Given inputs and output, enumerate all programs in the search space until 
			find a solution p such that output ⊆ subseteq p(inputs)  """
		all_sketches = self.enum_sketches(size=max_prog_size, num_inputs=len(inputs))
		concrete_programs = []
		for level, sketches in all_sketches.items():
			for s in sketches:
				concrete_programs += self.iteratively_instantiate_and_print(s, inputs, 1)
		for p in concrete_programs:
			try:
				t = p.eval(inputs)
				if check_table_inclusion(output, t.to_dict(orient="records")):
					print(p.stmt_string())
					print(p.eval(inputs))
			except Exception as e:
				print(f"[error] {sys.exc_info()[0]} {e}")
				tb = sys.exc_info()[2]
				tb_info = ''.join(traceback.format_tb(tb))
				print(tb_info)
		print("----")
		print(f"number of programs: {len(concrete_programs)}")


	def enumerative_synthesis(self, inputs, output, max_prog_size):
		"""Given inputs and output, enumerate all programs with premise check until 
			find a solution p such that output ⊆ subseteq p(inputs) """
		all_sketches = self.enum_sketches(size=max_prog_size, num_inputs=len(inputs))
		for level, sketches in all_sketches.items():
			for s in sketches:
				ast = s.to_dict()
				out_df = pd.DataFrame.from_dict(output)
				out_df = remove_duplicate_columns(out_df)
				# all premise chains for the given ast
				premise_chains = abstract_eval.backward_eval(ast, out_df)
				for premise_chain in premise_chains:
					#concrete_programs = instantiate_with_premise_check(p, inputs, premise_chain)
					candidates = self.iteratively_instantiate_with_premise_check(s, inputs, premise_chain)
					for p in candidates:
						t = p.eval(inputs)
						if check_table_inclusion(output, t.to_dict(orient="records")):
							print(p.stmt_string())
							print(p.eval(inputs))

	def enumerative_synthesis_v2(self, inputs, output, max_prog_size):
		"""Given inputs and output, enumerate all programs with premise check until 
			find a solution p such that output ⊆ subseteq p(inputs) """
		all_sketches = self.enum_sketches(size=max_prog_size, num_inputs=len(inputs))
		for level, sketches in all_sketches.items():
			for s in sketches:
				ast = s.to_dict()
				out_df = pd.DataFrame.from_dict(output)
				out_df = remove_duplicate_columns(out_df)
				# all premise chains for the given ast
				premise_chains = abstract_eval.backward_eval(ast, out_df)
				#concrete_programs = instantiate_with_premise_check(p, inputs, premise_chain)
				candidates = self.iteratively_instantiate_with_premises_check(s, inputs, premise_chains)
				for p in candidates:
					t = p.eval(inputs)
					if check_table_inclusion(output, t.to_dict(orient="records")):
						print(p.stmt_string())
						print(p.eval(inputs))


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
	#Synthesizer().enumerative_search(inputs, output, 3)
	Synthesizer().enumerative_synthesis_v2(inputs, output, 3)