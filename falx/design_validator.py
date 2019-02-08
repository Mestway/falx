from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import jsonschema
import subprocess
import sys

def get_attr(obj, attr):
	return obj[attr] if attr in obj else None

def internal_validation(spec):
	for enc in spec["encoding"]:
		if not validate_encoding(enc):
			return False
	return cross_encoding_validation(spec)

def fieldtype_compatibility_check(spec, field_metadata):
	"""check compatibility of fields with the encodings. """
	for enc in spec["encoding"]:
		if not validate_field_type(enc, field_metadata):
			return False
	return True


def channel_discrete(enc):
	return enc["type"] in ["nominal", "ordinal"] or get_attr(enc, "bin")

def channel_continuous(enc):
	return not channel_discrete(enc)

def get_orientation(spec):
	"""get orientation of a spec, whether 'vertical' or 'horizontal' """

	channels = [enc["channel"] for enc in spec["encoding"]]
	x_enc = None if "x" not in channels else [enc for enc in spec["encoding"] if enc["channel"] == "x"][0]
	y_enc = None if "y" not in channels else [enc for enc in spec["encoding"] if enc["channel"] == "y"][0]

	if spec["mark"] in ["bark", "tick", "area", "line"] and x_enc is not None and channel_discrete(x_enc):
		return "vertical" 
	elif spec["mark"] in ["area", "line"] and channel_continuous(x_enc) and channel_continuous(y):
		return "vertical"
	elif spec["mark"] in ["bark", "tick", "area", "line"] and channel_discrete(y):
		return "horizontal"
	else:
		print("[err] unable to determine horizontal or vertical for the following spec")
		print(json.dumps(spec))
		sys.exit(-1)		

def cross_encoding_validation(spec):
	"""validate the spec cross encodings """

	encodings = spec["encoding"]
	channels = [enc["channel"] for enc in encodings]
	
	x_enc = None if "x" not in channels else [enc for enc in encodings if enc["channel"] == "x"][0]
	y_enc = None if "y" not in channels else [enc for enc in encodings if enc["channel"] == "y"][0]

	# Cannot use single channels twice.
	if len(channels) != len(set(channels)): return False

	# There has to be at least one encoding. Otherwise, the visualization doesn't show anything.
	if len(encodings) == 0: return False

	# Row and column require discrete. [see validate_encoding]

	# Don't use row without y. Just using y is simpler.
	if "row" in channels and not "y" in channels: return False

	# Don't use column without x. Just using x is simpler.
	if "column" in channels and not "x" in channels: return False

	# All encodings (if they have a channel) require field except if we have a count aggregate. [moved to validate_encoding]
	# Count should not have a field. Having a field doesn't make a difference. [moved to validate_encoding]

	# Text mark requires text channel; Text channel requires text mark.
	if (spec["mark"] == "text" and "text" not in "channel") or ("text" in "channel" and spec["mark"] != "text"): return False

	# Point, tick, and bar require x or y channel.
	if spec["mark"] in ["point", "tick", "bark"] and not ("x" in channels or "y" in channels): return False
	
	if spec["mark"] in ["line", "area"]:
		# Line and area require x and y channel.
		if not ("x" in channels and "y" in channels): 
			return False
		# Line and area cannot have two discrete.
		if channel_discrete(x_enc) and channel_discrete(y_enc):
			return False

	# Bar and tick cannot have both x and y continuous.
	if spec["mark"] in ["bar", "tick"]:
		if "x" in channels and "y" in channels:
			if channel_continuous(x_enc) and channel_continuous(y_enc):
				return False
	
	# Bar, tick, line, area require some continuous variable on x or y.
	if spec["mark"] in ["bar", "tick", "area", "line"]:
		if not ((x_enc != None and channel_continuous(x_enc)) or (y_enc != None and channel_continuous(y_enc))):
			return False

	# Bar and area mark requires scale of continuous to start at zero.
	if spec["mark"] in ["bark", "area"]:
		if get_orientation(spec) == "horizontal" and not get_attr(x_enc, "zero"): 
			return False
		if get_orientation(spec) == "vertical" and not get_attr(y_enc, "zero"):
			return False

	# Shape channel requires point mark.
	if "shape"in channels and spec["mark"] != "point": 
		return False

	# Size only works with some marks. Vega-Lite can also size lines, and ticks but that would violate best practices.
	if "size" in channels and spec["mark"] not in ["point", "text"]:
		return False

	# Detail requires aggregation. Detail adds a field to the group by. 
	# Detail could also be used to add information to tooltips. We may remove this later.
	if "detail" in "channels" and len([enc for enc in encodings if "aggregate" in enc]) == 0: return False

	# Do not use log for bar or area mark as they are often misleading. We may remove this rule in the future.
	if spec["mark"] in ["bar", "area"] and (x_enc is not None and "log" in x_enc) and (y_enc is not None and "log" in y_enc):
		return False

	# Rect mark needs discrete x and y.
	if spec["mark"] == "rect" and not (channel_discrete(x_enc) and channel_discrete(y_enc)): return False

	# Don't use the same field on x and y.
	if x_enc and y_enc and (x_enc["channel"] == y_enc["channel"]): return False

	# Don't use count on x and y.
	if (x_enc and get_attr(x_enc, "count")) or (y_enc and get_attr(y_enc, "count")): return False

	# If we use aggregation, then all continuous fields need to be aggeragted.
	if (len([enc for enc in encodings if get_attr(enc, "aggregate")]) > 0 
		and len([enc for enc in encodings if channel_continuous(enc) and "aggregate" not in enc]) > 0):
		return False

	# Don't use count twice.
	if len([enc for enc in encodings if get_attr(enc, "aggregate") == "count"]) >= 2:
		return False

	return True


def validate_encoding(enc):
	"""validate whether an encoding is valid or not """

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

	# All encodings (if they have a channel) require field except if we have a count aggregate.
	if get_attr(enc, "aggregate") != "count" and "field" not in enc: return False

	# Shape requires discrete and not ordered (nominal). Using ordinal would't make a difference in Vega-Lite.
	if enc["channel"] == "shape" and enc["type"] != "nominal": return False

	# Detail requires nominal
	if enc["channel"] == "detail" and enc["type"] != "nominal": return False

	# Size implies ordr so nominal is misleading
	if enc["channel"] == "size" and enc["type"] == "nominal": return False

	# Row and column require discrete
	if enc["channel"] in ["row", "column"] and not channel_discrete(enc): return False

	return True

def validate_field_type(enc, field_metadata):
	"""fieldtype related validation """

	field_type = field_metadata[enc["field"]]["type"] if "field" in enc else None
	field_min_max = (field_metadata[enc["field"]]["min"], field_metadata[enc["field"]]["max"]) if "field" in enc and field_type == "number" else None

	# Primitive type has to support data type
	if enc["type"] == "temporal" and field_type != "datetime": return False
	if enc["type"] in ["quantitative", "ordinal"] and field_type in ["string", "boolean"]: return False

	# Cannot use log if the data is negative or zero
	if (get_attr(enc, "scale") and get_attr(get_attr(enc, "scale"), "log") and 
		field_min_max and field_min_max[0] <= 0):
		return False

	# Do not use size when data is negative as size implies that data is positive.
	if enc["channel"] == "size" and field_min_max and field_min_max[0] <= 0: return False

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