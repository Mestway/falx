from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json

def load_spec(input_file):
	with open(input_file, "r") as f:
		vl_spec = json.load(f)
	return vl_spec

