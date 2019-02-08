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
	"aggregate": [None], #, "max", "sum"],
	"bin": [None],
	"summative_aggregate_op": ["count", "sum"],
}

ENUM_DOMAINS = {
	#"/mark": DOMAINS["mark"],
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


def enum_specs(spec, max_changes=1):
	"""enumerate specs out of an existing vl_json. """
	
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

			if not design_validator.internal_validation(new_spec):
				continue

			outputs.append(new_spec)

	return outputs


def equiv_design_abstraction():
	pass


def explore_designs(example_vl, target_data, target_fields):
	"""given an example vl, explore alternatives """
	results = []
	example_vl["data"] = target_data
	example_vl = example_vl.copy()
	for enc in example_vl["encoding"]:
		if "field" in enc:
			enc["field"] = None

	needed_fields = len([k for k in example_vl["encoding"] if "field" in example_vl["encoding"][k]])

	if len(target_fields) != needed_fields:
		return []

	candidates = enum_specs(utils.vl2obj(example_vl))

	field_permutations = list(itertools.permutations(list(target_fields.keys())))

	for candidate_spec in candidates:
		for fields in field_permutations:
			temp_spec = candidate_spec.copy()

			for i in range(len(temp_spec["encoding"])):
				temp_spec["encoding"][i]["field"] = fields[i]

			if design_validator.fieldtype_compatibility_check(temp_spec, target_fields):
				temp_vl_spec = utils.obj2vl(temp_spec)
				results.append(temp_vl_spec)

	return results