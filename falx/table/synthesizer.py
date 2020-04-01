import sys
import traceback
import copy
from pprint import pprint
import pandas as pd
import time

from falx.table.language import (HOLE, Node, Table, Select, Unite, Filter, Separate, Spread, 
	Gather, GroupSummary, CumSum, Mutate, MutateCustom)
from falx.table import enum_strategies
from falx.table import abstract_eval
from falx.utils.synth_utils import remove_duplicate_columns, check_table_inclusion, align_table_schema

abstract_combinators = {
	"select": lambda q: Select(q, cols=HOLE),
	"unite": lambda q: Unite(q, col1=HOLE, col2=HOLE),
	"filter": lambda q: Filter(q, col_index=HOLE, op=HOLE, const=HOLE),
	"separate": lambda q: Separate(q, col_index=HOLE),
	"spread": lambda q: Spread(q, key=HOLE, val=HOLE),
	"gather": lambda q: Gather(q, value_columns=HOLE),
	"group_sum": lambda q: GroupSummary(q, group_cols=HOLE, aggr_col=HOLE, aggr_func=HOLE),
	"cumsum": lambda q: CumSum(q, target=HOLE),
	"mutate": lambda q: Mutate(q, col1=HOLE, op=HOLE, col2=HOLE),
	"mutate_custom": lambda q: MutateCustom(q, col=HOLE, op=HOLE, const=HOLE), 
}

def update_tree_value(node, path, new_val):
	"""from a given ast node, locate the refence to the arg,
	   and update the value"""
	for k in path:
		node = node["children"][k]
	node["value"] = new_val

def get_node(node, path):
	for k in path:
		node = node["children"][k]
	return node

class Synthesizer(object):

	def __init__(self, config=None):
		if config is None:
			self.config = {
				"operators": ["select", "unite", "filter", "separate", "spread", 
					"gather", "group_sum", "cumsum", "mutate", "mutate_custom"],
				"filer_op": [">", "<", "=="],
				"constants": [],
				"aggr_func": ["mean", "sum", "count"],
				"mutate_op": ["+", "-"],
				"gather_max_val_list_size": 3,
				"gather_max_key_list_size": 3
			}
		else:
			self.config = config

	def enum_sketches(self, inputs, output, size):
		"""enumerate program sketches up to the given size"""

		# check if output contains a new value 
		# (this decides if we should use ops that generates new vals)
		
		inp_val_set = set([v for t in inputs for r in t for k, v in r.items()] + [k for t in inputs for k in t[0]])
		out_val_set = set([v for r in output for k, v in r.items()])
		new_vals = out_val_set - inp_val_set
		
		#if any([len(t[0]) < 4 for t in inputs]):
			# always consider new value operators for small tables (#column < 4)
		#	contain_new_val = True

		# check if there are seperators in column names
		sep_in_col_names = [key for t in inputs for key in t[0] if ('-' in key or '_' in key or '/' in key)]
		sep_in_content = [v for t in inputs for r in t for k, v in r.items() if (isinstance(v, str) and ('-' in v or '_' in v or '/' in v))]
		has_sep = (len(sep_in_col_names) > 0) or (len(sep_in_content) > 0)

		candidates = {}
		for level in range(0, size + 1):
			candidates[level] = []
			if level == 0:
				candidates[level] += [Table(data_id=i) for i in range(len(inputs))]
			else:
				for p in candidates[level - 1]:
					for op in abstract_combinators:
						#ignore operators that are not set
						if op not in self.config["operators"]:
							continue
						q = abstract_combinators[op](copy.copy(p))
						if not enum_strategies.disable_sketch(q, new_vals, has_sep):
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

	def iteratively_instantiate_with_premises_check(self, p, inputs, premise_chains, time_limit_sec=None):
		"""iteratively instantiate abstract programs w/ promise check """
		
		print("time limit: {}".format(time_limit_sec))
		if time_limit_sec < 0:
			return []

		start_time = time.time()

		def instantiate_with_premises_check(p, inputs, premise_chains):
			"""instantiate programs and then check each one of them against the premise """
			results = []
			if p.is_abstract():

				print(p.stmt_string())
				ast = p.to_dict()
				next_level_programs, level = self.instantiate_one_level(ast, inputs)

				for _ast in next_level_programs:

					# force terminate if the remaining time is running out
					if time_limit_sec is not None and time.time() - start_time > time_limit_sec:
						return results

					premises_at_level = [[pm for pm in premise_chain if len(pm[1]) == level][0] for premise_chain in premise_chains]

					subquery_res = None
					for premise, subquery_path in premises_at_level:

						if subquery_res is None:
							# check if the subquery result contains the premise
							subquery_node = get_node(_ast, subquery_path)
							print("  {}".format(Node.load_from_dict(subquery_node).stmt_string()))
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
				if time_limit_sec is not None and time.time() - start_time > time_limit_sec:
					return results
				remaining_time_limit = time_limit_sec - (time.time() - start_time) if time_limit_sec is not None else None
				results += self.iteratively_instantiate_with_premises_check(_p, inputs, premise_chains, remaining_time_limit)
			return results
		else:
			return [p]

	def enumerative_all_programs(self, inputs, output, max_prog_size):
		"""Given inputs and output, enumerate all programs in the search space until 
			find a solution p such that output ⊆ subseteq p(inputs)  """
		all_sketches = self.enum_sketches(inputs, output, size=max_prog_size)
		concrete_programs = []
		for level, sketches in all_sketches.items():
			for s in sketches:
				concrete_programs += self.iteratively_instantiate_and_print(s, inputs, 1, True)
		for p in concrete_programs:
			try:
				t = p.eval(inputs)
				print(p.stmt_string())
				print(t)
			except Exception as e:
				print(f"[error] {sys.exc_info()[0]} {e}")
				tb = sys.exc_info()[2]
				tb_info = ''.join(traceback.format_tb(tb))
				print(tb_info)
		print("----")
		print(f"number of programs: {len(concrete_programs)}")

	def enumerative_search(self, inputs, output, max_prog_size):
		"""Given inputs and output, enumerate all programs in the search space until 
			find a solution p such that output ⊆ subseteq p(inputs)  """
		all_sketches = self.enum_sketches(inputs, output, size=max_prog_size)
		candidates = []
		for level, sketches in all_sketches.items():
			for s in sketches:
				concrete_programs = self.iteratively_instantiate_and_print(s, inputs, 1)
				for p in concrete_programs:
					try:
						t = p.eval(inputs)
						if align_table_schema(output, t.to_dict(orient="records")) != None:
							print(p.stmt_string())
							print(t)
							candidates.append(p)
					except Exception as e:
						print(f"[error] {sys.exc_info()[0]} {e}")
						tb = sys.exc_info()[2]
						tb_info = ''.join(traceback.format_tb(tb))
						print(tb_info)
		print("----")
		print(f"number of programs: {len(candidates)}")
		return candidates

	def enumerative_synthesis(self, inputs, output, max_prog_size, time_limit_sec=None, solution_limit=None):
		"""Given inputs and output, enumerate all programs with premise check until 
			find a solution p such that output ⊆ subseteq p(inputs) """

		start_time = time.time()

		all_sketches = self.enum_sketches(inputs, output, size=max_prog_size)
		candidates = []
		for level, sketches in all_sketches.items():
			for s in sketches:
				print(s.stmt_string())
				ast = s.to_dict()
				out_df = pd.DataFrame.from_dict(output)

				out_df = remove_duplicate_columns(out_df)
				# all premise chains for the given ast
				premise_chains = abstract_eval.backward_eval(ast, out_df)

				remaining_time_limit = time_limit_sec - (time.time() - start_time) if time_limit_sec is not None else None
				programs = self.iteratively_instantiate_with_premises_check(s, inputs, premise_chains, remaining_time_limit)
				
				for p in programs:
					# check table consistensy
					t = p.eval(inputs)
					alignment_result = align_table_schema(output, t.to_dict(orient="records"))
					if alignment_result != None:
						candidates.append(p)

					if solution_limit is not None and len(candidates) > solution_limit:
						return candidates
				
				# early return if the termination condition is met
				# TODO: time_limit may be exceeded if the synthesizer is stuck on iteratively instantiation
				if time_limit_sec is not None and time.time() - start_time > time_limit_sec:
					return candidates


		return candidates
