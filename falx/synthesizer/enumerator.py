import copy
from pprint import pprint

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

def enum_sketches(size, num_inputs):
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

def instantiate(p, inputs):
	return p


def enumerative_synthesis(inputs, output):
	candidates = enum_sketches(size=1, num_inputs=len(inputs))
	for level, programs in candidates.items():
		for p in programs:
			ast = p.to_dict()
			#print("---")
			#print(ast)
			#print(Node.load_from_dict(ast).to_dict())
			print(p.stmt_string())

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
	enumerative_synthesis(inputs, output)