import argparse
import json
import pandas as pd
import os
from pprint import pprint

import design_validator
import design_enumerator
import utils

import morpheus

# default directories
PROJ_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DATA_DIR = os.path.join(PROJ_DIR, "benchmarks")
TEMP_DIR = os.path.join(PROJ_DIR, "__temp__")
if not os.path.exists(TEMP_DIR): os.mkdir(TEMP_DIR)

# arguments
parser = argparse.ArgumentParser()
parser.add_argument("--data_dir", dest="data_dir", default=DATA_DIR, help="the directory of all benchmarks")
parser.add_argument("--output_dir", dest="output_dir", default=TEMP_DIR, help="output directory")

def load_dataset(data_dir):
	"""load the dataset into panda dataframes """
	dataset = []
	print("=======")
	for fname in os.listdir(data_dir):
		#if "031.json" not in fname: continue
		if fname.endswith(".json"):
			with open(os.path.join(data_dir, fname), "r") as f:
				data = json.load(f)
			input_data = pd.read_json(json.dumps(data["input_data"]))
			# infer type of each column and then update column value
			for col in input_data:
				dtype, new_col_values = utils.clean_column_dtype(input_data[col])
				input_data[col] = new_col_values
				print(col, ":", dtype)
				#print(input_data[col])
				#print(list(input_data[col]))

			dataset.append(input_data)
			print(input_data)
	return dataset


def run(flags):
	"""Synthesize vega-lite schema """
	dataset = load_dataset(flags.data_dir)


if __name__ == '__main__':
	flags = parser.parse_args()
	run(flags)
