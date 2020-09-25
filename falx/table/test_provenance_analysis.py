import unittest

from falx.table.language import *
from falx.table.provenance_analysis import *
import os
import pandas as pd

from pprint import pprint

class TestProvenanceAnalysis(unittest.TestCase):


	def test_table_ref(self):

		print("===")
		q = Table(data_id=0)

		node = q.to_dict()
		print(q.stmt_string())

		inputs = [[
			{ "Bucket": "Bucket_E", "Budgeted": 100, "Actual": 115 },
			{ "Bucket": "Bucket_D", "Budgeted": 100, "Actual": 90 },
			{ "Bucket": "Bucket_C", "Budgeted": 125, "Actual": 115 },
			{ "Bucket": "Bucket_B", "Budgeted": 125, "Actual": 140 },
			{ "Bucket": "Bucket_A", "Budgeted": 140, "Actual": 150 }
		]]

		output = [
			{ "Bucket": "Bucket_E", "Budgeted": 100},
			{ "Bucket": "Bucket_D", "Budgeted": 100}
		]

		out_df = pd.DataFrame.from_dict(output)

		pred, trimmed_inputs = provenance_analysis(node, out_df, inputs)

		print(pred.print_str())
		print(pd.DataFrame(trimmed_inputs[0]))

	def test_unite(self):
		print("===")
		q = Table(data_id=0)
		q = Unite(q, 0, 1)

		node = q.to_dict()

		print(q.stmt_string())

		inputs = [[
			{ "Bucket": "Bucket", "ID": "E", "Budgeted": 100, "Actual": 115 },
			{ "Bucket": "Bucket", "ID": "D", "Budgeted": 100, "Actual": 90 },
			{ "Bucket": "Bucket", "ID": "C", "Budgeted": 125, "Actual": 115 },
			{ "Bucket": "Bucket", "ID": "B", "Budgeted": 125, "Actual": 140 },
			{ "Bucket": "Bucket", "ID": "A", "Budgeted": 140, "Actual": 150 }
		]]

		output = [
			{"y": 115,  "column": "Bucket_E"},
			{"y": 100, "column": "Bucket_D"},
		]

		out_df = pd.DataFrame.from_dict(output)

		pred, trimmed_inputs = provenance_analysis(node, out_df, inputs)

		print(pred.print_str())
		print(pd.DataFrame(trimmed_inputs[0]))

	def test_separate(self):
		print("===")
		q = Table(data_id=0)
		q = Separate(q, 0)

		node = q.to_dict()

		print(q.stmt_string())

		inputs = [[
			{ "Bucket": "Bucket_E", "Budgeted": 100, "Actual": 115 },
			{ "Bucket": "Bucket_D", "Budgeted": 100, "Actual": 90 },
			{ "Bucket": "Bucket_C", "Budgeted": 125, "Actual": 115 },
			{ "Bucket": "Bucket_B", "Budgeted": 125, "Actual": 140 },
			{ "Bucket": "Bucket_A", "Budgeted": 140, "Actual": 150 }
		]]

		output = [
			{"y": 115,  "column": "E"},
			{"y": 125, "column": "C"},
		]

		out_df = pd.DataFrame.from_dict(output)

		pred, trimmed_inputs = provenance_analysis(node, out_df, inputs)

		print(pred.print_str())
		print(pd.DataFrame(trimmed_inputs[0]))

	def test_mutate(self):
		print("===")
		q = Table(data_id=0)
		q = Mutate(q, 1, "+", 2)

		node = q.to_dict()

		print(q.stmt_string())

		inputs = [[
			{ "Bucket": "Bucket", "ID": "E", "Budgeted": 100, "Actual": 115 },
			{ "Bucket": "Bucket", "ID": "D", "Budgeted": 100, "Actual": 90 },
			{ "Bucket": "Bucket", "ID": "C", "Budgeted": 125, "Actual": 115 },
			{ "Bucket": "Bucket", "ID": "B", "Budgeted": 125, "Actual": 140 },
			{ "Bucket": "Bucket", "ID": "A", "Budgeted": 140, "Actual": 150 }
		]]

		output = [
			{"y": 215,  "column": "E"},
			{"y": 190, "column": "D"},
		]

		out_df = pd.DataFrame.from_dict(output)

		pred, trimmed_inputs = provenance_analysis(node, out_df, inputs)

		print(pred.print_str())
		print(pd.DataFrame(trimmed_inputs[0]))

	def test_unite_mutate(self):
		print("===")
		q = Table(data_id=0)
		q = Mutate(q, 1, "+", 2)
		q = Unite(q, 0, 1)

		node = q.to_dict()

		print(q.stmt_string())

		inputs = [[
			{ "Bucket": "Bucket", "ID": "E", "Budgeted": 100, "Actual": 115 },
			{ "Bucket": "Bucket", "ID": "D", "Budgeted": 100, "Actual": 90 },
			{ "Bucket": "Bucket", "ID": "C", "Budgeted": 125, "Actual": 115 },
			{ "Bucket": "Bucket", "ID": "B", "Budgeted": 125, "Actual": 140 },
			{ "Bucket": "Bucket", "ID": "A", "Budgeted": 140, "Actual": 150 }
		]]

		output = [
			{"y": 215,  "column": "Bucket_E"},
			{"y": 190, "column": "Bucket_D"},
		]

		out_df = pd.DataFrame.from_dict(output)

		pred, trimmed_inputs = provenance_analysis(node, out_df, inputs)

		print(pred.print_str())
		print(pd.DataFrame(trimmed_inputs[0]))

	def test_unite_gather(self):
		print("===")
		q = Table(data_id=0)
		q = Gather(q, [2, 3])
		q = Unite(q, 0, 1)

		node = q.to_dict()

		print(q.stmt_string())

		inputs = [[
			{ "Bucket": "Bucket", "ID": "E", "Budgeted": 100, "Actual": 115 },
			{ "Bucket": "Bucket", "ID": "D", "Budgeted": 100, "Actual": 90 },
			{ "Bucket": "Bucket", "ID": "C", "Budgeted": 125, "Actual": 115 },
			{ "Bucket": "Bucket", "ID": "B", "Budgeted": 125, "Actual": 140 },
			{ "Bucket": "Bucket", "ID": "A", "Budgeted": 140, "Actual": 150 }
		]]

		output = [
			{"y": 100,  "column": "Bucket_E"},
			{"y": 90, "column": "Bucket_D"},
		]

		out_df = pd.DataFrame.from_dict(output)

		pred, trimmed_inputs = provenance_analysis(node, out_df, inputs)

		print(pred.print_str())
		print(pd.DataFrame(trimmed_inputs[0]))

	def test_gather(self):

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

if __name__ == '__main__':
    unittest.main()