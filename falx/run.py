from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import argparse

def run(args):
	print(args)

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument("--input_dir", dest="input_dir", default=None, help="input directory")
	parser.add_argument("--output_dir", dest="output_dir", default=None, help="output directory")
	args = parser.parse_args()
	run(args)