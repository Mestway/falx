from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import argparse
import os
from pprint import pprint

import transformer
import util

# default directories
proj_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
temp_dir = os.path.join(proj_dir, "__temp__")
if not os.path.exists(temp_dir): os.mkdir(temp_dir)

# arguments
parser = argparse.ArgumentParser()
parser.add_argument("--input_file", dest="input_file", default=None, 
					help="input Vega-Lite spec file")
parser.add_argument("--input_dir", dest="input_dir",
					default=os.path.join(proj_dir, "vl_examples"),
					help="input files; ignored if input-file is specified")
parser.add_argument("--output_dir", dest="output_dir", 
					default=temp_dir, help="output directory")


def run(flags):
	input_files = []
	if flags.input_file is not None:
		input_files.append(flags.input_file)
	else:
		for fname in os.listdir(flags.input_dir):
			if fname.endswith(".vl.json"):
				input_files.append(os.path.join(flags.input_dir, fname))

	vl_specs = [util.load_vl_spec(f) for f in input_files]
	data_urls = [spec["data"]["url"] for spec in vl_specs if "url" in spec["data"]]

	for vl_spec in vl_specs:
		if "layer" in vl_spec:
			continue
		out_vl_specs = transformer.enum_specs(vl_spec)
		for s in out_vl_specs:
			pass #print(s)
		break

if __name__ == '__main__':
	flags = parser.parse_args()
	run(flags)