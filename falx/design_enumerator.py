from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import itertools
import json
import jsonschema
import os
from pprint import pprint
import subprocess
import sys

import dpath

import utils

DOMAINS = {
	"/mark": ["point", "bar", "line", "area"],
	"/encoding/*/type": ["quantitative", "ordinal", "nominal", "temporal"],
	#"primitive_type": ["string", "number", "boolean", "datetime"],
	"/encoding/*/aggregate": [None, "count", "min", "max", "sum"],
	"/encoding/*/bin": [None, 10],
}

def get_attr(obj, attr):
	return obj[attr] if attr in obj else None

def instantiate_domains(domains, encoding_cnt):
	"""create domain for fields we want to encode. """
	instantiated = {}
	for d in domains:
		if "/encoding/*" in d:
			for i in range(encoding_cnt):
				instantiated[d.replace("/encoding/*", f"/encoding/{i}")] = domains[d]
		else:
			instantiated[d] = domains[d]
	return instantiated

def explore_designs(example_vl, target_data, target_fields):
	"""given an example vl, explore alternatives """
	results = []
	example_vl["data"] = target_data
	fields_permutations = itertools.permutations(target_fields.keys())
	for p in fields_permutations:
		temp_vl_json = example_vl.copy()
		for i, k in enumerate(temp_vl_json["encoding"]):
			temp_vl_json["encoding"][k]["field"] = p[i]
		candidates = enum_specs(temp_vl_json, target_fields)
		results.extend(candidates)
	return results

def enum_specs(vl_json, target_fields, max_changes=1):
	"""enumerate specs out of an existing vl_json. """
	
	spec = utils.vl2obj(vl_json)
	flat_spec = dict(utils.flatten_object(spec))

	domains = instantiate_domains(DOMAINS, len(spec["encoding"]))
	
	outputs = []
	for l in itertools.combinations(domains.keys(), r=max_changes):
		
		current_vals = dict([(f, flat_spec[f]) if f in flat_spec else (f, None) for f in l])
		candidates = [[(f, v) for v in domains[f] if v != current_vals[f]] for f in l]

		for updates in itertools.product(*candidates):
			new_flat_spec = flat_spec.copy()
			for p in updates:
				new_flat_spec[p[0]] = p[1]

			new_spec = utils.reconstruct_object(new_flat_spec.items()) 

			if not internal_validate_spec(new_spec, target_fields):
				continue

			new_vl_json = utils.obj2vl(new_spec)
			outputs.append(new_vl_json)

	return outputs

def internal_validate_spec(spec, field_metadata):
	for enc in spec["encoding"]:
		if not validate_encoding(enc, field_metadata):
			return False
	return True


def validate_encoding(enc, field_metadata):
#	print(enc)
#	print(field_metadata)
	if (field_metadata[enc['field']]["type"] == "str" 
		and enc['type'] in ["quantitative", "ordinal", "temporal"]):
		return False
	if (get_attr(enc, "bin") is not None and get_attr(enc, "aggregate") is not None):
		return False
	return True

def validate_spec(spec, vl_schema, external_validation=False):
	"""validate whether """
	message = []
	valid = True
	if external_validation:
		proc = subprocess.Popen(
			args=["node", utils.absolute_path("../js/index.js")],
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE
		)
		stdout, stderr = proc.communicate(json.dumps(spec).encode("utf8"))

		if stderr:
			message.append(stderr.decode("utf-8").strip())
		message.append(stdout.decode("utf-8").strip())
	try:
		jsonschema.validate(spec, vl_schema)
	except:
		valid = False

	return valid, message

