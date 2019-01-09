from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
from pprint import pprint
import dpath

import util

domains = {
	"mark": ["point", "bar", "line", "area", "text", "tick", "rect"],
	"encoding": [{
		"type": ["quantitative", "ordinal", "nominal", "temporal"],
		#"primitive_type": ["string", "number", "boolean", "datetime"],
		"aggregate": ["count", "mean", "median", "min", "max", "stdev", "sum"],
		"bin": [10, 25, 100],
	}],
}


def enum_specs(vl_spec, max_changes=1):
	"""enumerate specs out of an existing vl_spec. """
	
	spec = util.vl2obj(vl_spec)
	pprint(spec)

	out_vl_specs = []

	print(util.resolve_field_paths(domains))

	for field in util.resolve_field_paths(domains):
		new_spec = vl_spec.copy()

		print("---")
		print(field)
		print(dpath.get(new_spec, field))


		if util.check_validatiy(new_spec):
			out_vl_specs.append(new_spec)

	return out_vl_specs
