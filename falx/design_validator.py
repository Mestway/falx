from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import jsonschema
import subprocess
import sys

def get_attr(obj, attr):
	return obj[attr] if attr in obj else None

def internal_validation(spec, field_metadata):
	for enc in spec["encoding"]:
		if not validate_encoding(enc, field_metadata):
			return False
	return True

def validate_encoding(enc, field_metadata):
	"""validate whether an encoding is valid or not """

	def discrete(e):
		return e["type"] in ["nominal", "ordinal"] or get_attr(e, "bin")

	field_type = field_metadata[enc["field"]]["type"] if "field" in enc else None

	# Primitive type has to support data type
	if enc["type"] == "temporal" and field_type != "datetime": return False
	if enc["type"] in ["quantitative", "ordinal"] and field_type in ["string", "boolean"]: return False

	# Can only bin quantitative or ordinal.
	if get_attr(enc, "bin") and enc["type"] not in ["quantitative", "ordinal"]: 
		return False

	# Can only use log / zero with quantitative.
	if (get_attr(enc, "zero") or get_attr(enc, "log")) and enc["type"] != "quantitative": 
		return False

	# Cannot use log scale with discrete (which includes binned).
	if get_attr(enc, "log") and discrete(enc): return False

	# Cannot use log and zero together
	if get_attr(enc, "zero") and get_attr(enc, "log"): return False

	# TODO Cannot use log if the data is negative or zero
	
	# Cannot bin and aggregate
	if get_attr(enc, "bin") and get_attr(enc, "aggregate"): return False

	# Oridnal only supports min, max, and median.
	if enc["type"] == "ordinal" and get_attr(enc, "aggregate") in ["min", "max", "medium"]: 
		return False

	# Temporal only supports min and max.
	if enc["type"] == "temporal" and get_attr(enc, "aggregate") in ["min", "max"]:
		return False

	# Cannot aggregate nominal.
	if enc["type"] == "nominal" and get_attr(enc, "aggregate"): return False

	# Detail cannot be aggregated
	if enc["channel"] == "detail" and get_attr(enc, "aggregate"): return False

	# Count has to be quantitative and not using a field
	if get_attr(enc, "aggregate") == "count" and get_attr(enc, "field"): return False
	if get_attr(enc, "aggregate") == "count" and enc["type"] != "quantitative": return False

	# Shape requires discrete and not ordered (nominal). Using ordinal would't make a difference in Vega-Lite.
	if enc["channel"] == "shape" and enc["type"] != "nominal": return False

	# Detail requires nominal
	if enc["channel"] == "detail" and enc["type"] != "nominal": return False

	# Size implies ordr so nominal is misleading
	if enc["channel"] == "size" and enc["type"] == "nominal": return False

	# TODO: Do not use size when data is negative as size implies that data is positive.

	return True

def external_validation(spec, vl_schema):
	"""validate whether """
	message = []
	valid = True

	## TODO test the following snippet later
	# if external_validation:
	# 	proc = subprocess.Popen(
	# 		args=["node", utils.absolute_path("../js/index.js")],
	# 		stdin=subprocess.PIPE,
	# 		stdout=subprocess.PIPE,
	# 		stderr=subprocess.PIPE
	# 	)
	# 	stdout, stderr = proc.communicate(json.dumps(spec).encode("utf8"))

	# 	if stderr:
	# 		message.append(stderr.decode("utf-8").strip())
	# 	message.append(stdout.decode("utf-8").strip())

	try:
		jsonschema.validate(spec, vl_schema)
	except:
		valid = False

	return valid, message