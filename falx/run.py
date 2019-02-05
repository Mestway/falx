from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import argparse
import json
import jsonschema
import os
from pprint import pprint

import design_validator
import design_enumerator
import utils

import morpheus_enumerator as morpheus

# default directories
PROJ_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
RESOURCE_DIR = os.path.join(PROJ_DIR, "resource")
TEMP_DIR = os.path.join(PROJ_DIR, "__temp__")
if not os.path.exists(TEMP_DIR): os.mkdir(TEMP_DIR)

# arguments
parser = argparse.ArgumentParser()
parser.add_argument("--input_chart_files", dest="input_chart_files", nargs='+',
					default=os.path.join(PROJ_DIR, "vl_examples", "rect_heatmap.vl.json"), 
					help="input Vega-Lite example files")
parser.add_argument("--input_data_files", dest="input_data_files", 
					default=os.path.join(PROJ_DIR, "benchmarks", "default.csv"), 
					help="input raw data in CSV files")
parser.add_argument("--output_dir", dest="output_dir", 
					default=TEMP_DIR, help="output directory")

parser.add_argument("--validation", dest="validation", default=0, type=int,
					help="whether to run additional validations for Vega-Lite specs,"
						 "Mode: 0 -- no extra validation"
						 "      1 -- schema check")


def run(flags):
	"""Synthesize vega-lite schema """

	with open(os.path.join(RESOURCE_DIR, "vega-lite-schema.json")) as f:
		vl_schema = json.load(f)

	input_chart_files = []
	g_list = morpheus.get_sample_data(flags.input_data_files)

	if flags.input_chart_files is not None:
		if isinstance(flags.input_chart_files, (list,)): 
			input_chart_files.extend(flags.input_chart_files)
		else:
			input_chart_files.append(flags.input_chart_files)

	vl_specs = [utils.load_vl_spec(f) for f in input_chart_files]
	data_urls = [spec["data"]["url"] for spec in vl_specs if "url" in spec["data"]]

	print("# start enumeration")
	
	output_index = 0
	for vl_spec in vl_specs:

		new_data = {"url": "data/unemployment-across-industries.json"}
		for morpheus_data in g_list:
			new_data = morpheus_data[0]
			target_fields = morpheus_data[1]

			candidates = design_enumerator.explore_designs(vl_spec, new_data, target_fields)
			
			for spec in candidates:
				if flags.validation == 1:
					# run external validation
					status, message = design_validator.external_validation(spec, vl_schema)
					if not status:
						print("x", end="", flush=True)
				print(".", end="", flush=True)
				with open(os.path.join(flags.output_dir, "temp_{}.vl.json".format(output_index)), "w") as g:
					g.write(json.dumps(spec))
				output_index += 1

	print("")
	print("# finish enumeration {}".format(output_index))

if __name__ == '__main__':
	flags = parser.parse_args()
	run(flags)
