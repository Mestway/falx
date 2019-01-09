from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json

def resolve_field_paths(obj):
	"""obtain xpaths for fields in an object. """
	paths = []

	if not isinstance(obj, (dict, )):
		return [""]

	for f in obj:
		if isinstance(obj[f], (list,)):
			for x in obj[f]:
				sub_paths = resolve_field_paths(x)
				if len(sub_paths) == 1 and sub_paths[0] == "":
					paths.append(f)
				else:
					for p in sub_paths:
						paths.append(f + "/*/"  + p)
		elif isinstance(obj[f], (dict,)):
			sub_paths = resolve_field_paths(obj[f])
			for p in sub_paths:
				paths.append(f + "/" + p)

	return list(set(paths))

def load_vl_spec(input_file):
	"""load vl specs from a json file. """
	with open(input_file, "r") as f:
		vl_spec = json.load(f)
	return vl_spec

def vl2obj(vl_spec):
	"""transforms an vl_spec to an object, modifying encodings"""
	spec = {}
	for f in vl_spec:
		if f == "encoding":
			spec[f] = []
			for v in vl_spec[f]:
				enc = vl_spec[f][v].copy()
				enc["channel"] = v
				spec[f].append(enc)
		else:
			spec[f] = vl_spec[f]
	return spec

def obj2vl(spec):
	"""reverse operator for vl2obj"""
	vl_spec = {}
	for f in spec:
		if f == "encoding":
			vl_spec[f] = {}
			for l in spec[f]:
				enc = l.copy()
				channel = enc.pop("channel", None)
				vl_spec[f][channel] = enc
		else:
			vl_spec[f] = spec[f]
	return vl_spec

def check_validatiy(vl_spec):
	"""check if a vl spec is valid"""
	return True
		