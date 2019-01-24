from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import os

def absolute_path(p):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), p)

def flatten_object(obj):
	"""flatten an object into paths for easier enumeration. 
		Args: an object
		Returns:
			a flat object with a list of pairs 
			[(p_1, v_1), ..., (p_k, v_k)], (paths and values)
		Example:
			{x: 1, y : {z: [a, b], w: c}} will be flatten into
			[("/x", 1), ("/y/z/0", a), ("/y/z/1", b), ("/y/w", c)]
	"""
	paths = []

	if isinstance(obj, (dict,)):
		for f in obj:
			sub_paths = flatten_object(obj[f])
			for p in sub_paths:
				paths.append(("/{}{}".format(f, p[0]), p[1]))
	elif isinstance(obj, (list,)):
		for i, x in enumerate(obj):
			sub_paths = flatten_object(x)
			for p in sub_paths:
				paths.append(("/{}{}".format(i, p[0]), p[1]))
	else:
		paths = [("", obj)]

	return paths

def reconstruct_object(flat_obj):
	"""reconstruct an object from flatten paths. 
		Args:
			flat_obj: a flat object with a list of pairs 
				[(p_1, v_1), ..., (p_k, v_k)], (paths and values)
		Returns:
			Either a primitive value, a list, or a dict 
			(depending on how the path is specified) 
	"""
	heads = list(set([x[0][1:].split('/')[0] for x in flat_obj]))

	# this is a primitive value
	if len(heads) == 1 and heads[0] == "":
		return flat_obj[0][1]

	# check if it is a list
	if all([v.isdigit() for v in heads]):
		heads = sorted([int(v) for v in heads])
		retval = list(range(len(heads)))
	else:
		retval = {}

	for h in heads:
		# recursively construct objects from paths
		prefix = "/{}".format(h)
		sub_paths = [(x[0][len(prefix):], x[1]) for x in flat_obj 
					 if x[0].startswith(prefix)]
		retval[h] = reconstruct_object(sub_paths)

	return retval

def load_vl_spec(input_file):
	"""load vl specs from a json file. """
	with open(input_file, "r") as f:
		vl_spec = json.load(f)
	return vl_spec

def vl2obj(vl_spec):
	"""transforms an vl_spec to an object,
	   it changes encodings from dict into list"""
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