from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import argparse
import os
from pprint import pprint

import transformer

# default directories
proj_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
temp_dir = os.path.join(proj_dir, "__temp__")
if not os.path.exists(temp_dir): os.mkdir(temp_dir)

# arguments
parser = argparse.ArgumentParser()
parser.add_argument("--input_file", dest="input_file", 
	default=os.path.join(proj_dir, "vl_examples", "histogram.vl.json"), 
	help="input Vega-Lite spec file")
parser.add_argument("--output_dir", dest="output_dir", 
	default=temp_dir, help="output directory")


def run(args):
	spec = transformer.load_spec(input_file=args.input_file)
	print(spec)


if __name__ == '__main__':
	
	args = parser.parse_args()
	run(args)