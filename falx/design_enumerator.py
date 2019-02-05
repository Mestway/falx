from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import dpath
import itertools
import json
import jsonschema
import os
from pprint import pprint
import sys

import design_validator
import utils

DOMAINS = {
	"mark": ["point", "bar", "line", "area", "text", "tick", "rect"],
	"primitive_type": ["string", "number", "boolean", "datetime"],
	"enc_type": ["quantitative", "ordinal", "nominal", "temporal"],
	"aggregate": [None, "count", "mean", "min", "max", "sum"],
	"bin": [None, 10, 25],
	"summative_aggregate_op": ["count", "sum"],
}

ENUM_DOMAINS = {
	"/mark": DOMAINS["mark"],
	"/encoding/*/type": DOMAINS["enc_type"],
	"/encoding/*/aggregate": DOMAINS["aggregate"],
	"/encoding/*/bin": DOMAINS["bin"],
}


def instantiate_domains(domains, encoding_cnt):
	"""create domain for fields we want to encode. """
	instantiated = {}
	for d in domains:
		if "/encoding/*" in d:
			for i in range(encoding_cnt):
				instantiated[d.replace("/encoding/*", "/encoding/{}".format(i))] = domains[d]
		else:
			instantiated[d] = domains[d]
	return instantiated


def explore_designs(example_vl, target_data, target_fields):
	"""given an example vl, explore alternatives """
	results = []
	example_vl["data"] = target_data
	fields_permutations = itertools.permutations(target_fields.keys())

	# enumerate over field combinations
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

	domains = instantiate_domains(ENUM_DOMAINS, len(spec["encoding"]))
	
	outputs = []
	for l in itertools.combinations(domains.keys(), r=max_changes):
		
		current_vals = dict([(f, flat_spec[f]) if f in flat_spec else (f, None) for f in l])
		candidates = [[(f, v) for v in domains[f] if v != current_vals[f]] for f in l]

		for updates in itertools.product(*candidates):
			new_flat_spec = flat_spec.copy()
			for p in updates:
				new_flat_spec[p[0]] = p[1]

			new_spec = utils.reconstruct_object(new_flat_spec.items()) 

			if not design_validator.internal_validation(new_spec, target_fields):
				continue

			new_vl_json = utils.obj2vl(new_spec)
			outputs.append(new_vl_json)

	return outputs



