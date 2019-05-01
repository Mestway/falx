import csv
import json
import os

import pandas as pd

def infer_dtype(values):
	return pd.api.types.infer_dtype(values, skipna=True)

def clean_column_dtype(column_values):
	dtype = pd.api.types.infer_dtype(column_values, skipna=True)

	if dtype != "string":
		return dtype, column_values

	def try_infer_string_type(values):
		"""try to infer datatype from values """
		dtype = pd.api.types.infer_dtype(values, skipna=True)
		ty_check_functions = [
			lambda l: pd.to_numeric(l),
			lambda l: pd.to_datetime(l, infer_datetime_format=True)
		]
		for ty_func in ty_check_functions:
			try:
				values = ty_func(values)
				dtype = pd.api.types.infer_dtype(values, skipna=True)
			except:
				pass
			if dtype != "stirng":
				break
		return dtype, values

	def to_time(l):
		return l[0] * 60 + l[1]

	convert_functions = {
		"id": (lambda l: True, lambda l: l),
		"percentage": (lambda l: all(["%" in x for x in l]), 
					   lambda l: [x.replace("%", "").replace(" ", "") if x.strip() not in [""] else "" for x in l]),
		"currency": (lambda l: True, lambda l: [x.replace("$", "").replace(",", "") for x in l]),
		"cleaning_missing_number": (lambda l: True, lambda l: [x if x.strip() not in [""] else "" for x in l]),
		"cleaning_time_value": (lambda l: True, lambda l: [to_time([int(y) for y in x.split(":")]) for x in l]),
	}

	for key in convert_functions:
		if convert_functions[key][0](column_values):
			try:
				converted_values = convert_functions[key][1](column_values)
			except:
				continue
			dtype, values = try_infer_string_type(converted_values)
		if dtype != "string": 
			if key == "percentage":
				values = values / 100.
			break
	return dtype, values


def load_and_clean_table(input_data):
	# infer type of each column and then update column value
	for col in input_data:
		dtype, new_col_values = clean_column_dtype(input_data[col])
		input_data[col] = new_col_values
	return input_data

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

def load_vl_spec(vl_spec_path, inline_data=True):
	"""load a vl spec and inline data as 'values' """
	abs_path = absolute_path(vl_spec_path)
	with open(vl_spec_path, "r") as f:
		vl_spec = json.load(f)

	if inline_data and "url" in vl_spec["data"]:
		data_path = vl_spec["data"]["url"]
		with open(os.path.join(os.path.dirname(abs_path), data_path), "r") as g:
			if data_path.endswith(".csv"):
				csv_reader = csv.DictReader(g)
				data = list([row for row in csv_reader])
			elif data_path.endswith(".json"):
				data = json.load(g)

		vl_spec["data"] = {"values": data}

	return vl_spec

def extract_data_props(vl_spec):
	"""extract properties of data """
	field_props = []
	vspec = vl2obj(vl_spec)
	data = vl_spec["data"]["values"]
	for enc in vspec["encoding"]:
		field_prop = {}
		if enc["field"] is not None:
			field_prop["field"] = enc["field"]
			field_prop["enc_type"] = enc["type"]
			column_values = [d[field_prop["field"]] for d in data]
			dtype = pd.api.types.infer_dtype(column_values)
			field_prop["dtype"] = dtype
			if dtype in ["integer", "float", "mixed-integer-float"]:
				field_prop["min"] = min(column_values)
				field_prop["max"] = max(column_values)
			field_prop["cardinality"] = len(set(column_values))
			field_props.append(field_prop)
	return field_props

