import argparse
import json
import pandas as pd
import os
from pprint import pprint

from chart import VisDesign
import design_validator
import design_enumerator
import table_utils

import morpheus

# default directories
PROJ_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DATA_DIR = os.path.join(PROJ_DIR, "benchmarks")

# arguments
parser = argparse.ArgumentParser()
parser.add_argument("--data_dir", dest="data_dir", default=DATA_DIR, help="the directory of all benchmarks")


def test_benchmarks(data_dir):
	"""load the dataset into panda dataframes """
	benchmarks = []
	for fname in os.listdir(data_dir):
		#if "031.json" not in fname: continue
		if fname.endswith(".json"):
			with open(os.path.join(data_dir, fname), "r") as f:
				data = json.load(f)

			if not "vl_spec" in data: continue

			print("======= {}".format(fname))

			input_data = table_utils.load_and_clean_table(pd.read_json(json.dumps(data["input_data"])))
			output_data = data["output_data"]
			vl_spec = data["vl_spec"]

			vis = VisDesign.load_from_vegalite(vl_spec, output_data)
			trace = vis.eval()

			#print(input_data)
			#print(output_data)
			#pprint(vl_spec)
			pprint(trace)


if __name__ == '__main__':
	flags = parser.parse_args()
	test_benchmarks(flags.data_dir)
