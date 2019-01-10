from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
from pprint import pprint
import dpath

import util

domains = {
	"mark": ["point", "bar", "line", "area", "text", "tick", "rect"],
	"type": ["quantitative", "ordinal", "nominal", "temporal"],
	#"primitive_type": ["string", "number", "boolean", "datetime"],
	"aggregate": ["count", "mean", "median", "min", "max", "stdev", "sum"],
	"bin": [10, 25, 100],
}

def enum_specs(vl_spec, max_changes=1):
	"""enumerate specs out of an existing vl_spec. """
	
	spec = util.vl2obj(vl_spec)
	flat_spec = util.flatten_object(spec)
	pprint(flat_spec)

	reconstr_spec = util.reconstruct_object(flat_spec)
	pprint(reconstr_spec)

	out_vl_specs = []

	return out_vl_specs
