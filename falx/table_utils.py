import json
import pandas as pd
import re

def infer_dtype(values):
	return pd.api.types.infer_dtype(values, skipna=True)

def filter_table(table, pred):
	"""convert js expression to python expression and then run eval """
	pred = pred.replace("&&", "and").replace("||", "or")
	pred = " ".join([v if "datum" not in v else "[\"".join(v.split(".")) + "\"]" for v in pred.split()])
	res = [datum for datum in table if eval(pred)]
	return res

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


def load_and_clean_dataframe(df):
	"""infer type of each column and then update column value
	Args:
		df: input dataframe we want to clean
	Returns:
		clean data frame
	"""
	for col in df:
		dtype, new_col_values = clean_column_dtype(df[col])
		df[col] = new_col_values
	return df


def load_and_clean_table(input_data, return_as_df=False):
	"""load and clean table where the input format is a table record """
	try:
		df = load_and_clean_dataframe(pd.DataFrame.from_dict(input_data))
		if return_as_df:
		 	return df
		else:
		 	return df.to_dict(orient="records")
	except:
		print("# [warning] error cleaning table, return without cleaning")
		return input_data
