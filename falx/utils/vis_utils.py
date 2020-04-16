import pandas as pd
import copy
import json

from falx.utils import table_utils

def gen_visual_trace_with_mult(_data, _fields):
	"""given a dataset and a few fields, returns the projection of the table on the fields
		the result is represented as a map that maps each tuple to its multiplicity
	"""
	visual_trace = [tuple([t[f] for f in _fields]) for t in _data]
	count_map = {}
	for tr in visual_trace:
		if tr not in count_map:
			count_map[tr] = 0
		count_map[tr] += 1
	return count_map

def break_down_layered(full_spec, data):
	layers = []
	for layer in full_spec["layer"]:
		spec = layer
		layer_id = spec["transform"][0]["filter"].split(" ")[-1]
		layer_data = [r for r in data if r["layer_id"] == int(layer_id)]
		layers.append((spec, layer_data))
	return layers

def is_broken_line_area_charts(layer_spec, raw_data):
	"""Given the spec and its corresponding data, filter undesirable data.
		This requires the input spec to be a single layer visualization, 
		if it is a multiple layer visualization, destruct layers first
	"""
	mark = layer_spec["mark"]["type"] if isinstance(layer_spec["mark"], (dict,)) else layer_spec["mark"]

	if mark not in ["line", "area"]:
		return False

	channel_field = []
	for ch in layer_spec["encoding"]:
		if ch == "order":
			continue
		enc = layer_spec["encoding"][ch]
		field_name = enc["field"]
		channel_field.append((ch, field_name))

	# print(channel_field)
		
	df = pd.DataFrame.from_dict(raw_data)
	df = df[[p[1] for p in channel_field]]

	data = df.to_dict(orient="records")

	non_pos_cols = [p[1] for p in channel_field if p[0] not in ["x", "y"]]
	x_col, y_col = [p[1] for p in channel_field if p[0] == "x"][0], [p[1] for p in channel_field if p[0] == "y"][0]

	partitions = {}
	for r in data:
		key = tuple([r[f] for f in non_pos_cols])
		if key not in partitions:
			partitions[key] = {}
		if r[x_col] not in partitions[key]:
			partitions[key][r[x_col]] = []
		partitions[key][r[x_col]].append(r[y_col])

	# print(partitions)

	if any([any([len(set(ys)) >= 2 for x, ys in p.items()]) for k1, p in partitions.items()]):
		print(" [Found broken line/area chart]")
		full_spec = copy.deepcopy(layer_spec)
		full_spec["data"] = {"values": raw_data}
		#print(json.dumps(full_spec))
		return True
			
	return False

def repair_broken_line_area_chart(layer_spec, data):
	"""add a new detail encoding for the spec to resolve ambiguity in line charts
		This requires the input spec to be a single layer visualization, 
		if it is a multiple layer visualization, destruct layers first
	"""
	used_fields = ["layer_id"] + [layer_spec["encoding"][ch]["field"] for ch in layer_spec["encoding"]]
	other_fields = [f for f in data[0] if f not in used_fields] + ([layer_spec["encoding"]["y"]["field"]] if "y" in layer_spec["encoding"] else [])

	candidates = []
	for f in other_fields:
		new_spec = copy.deepcopy(layer_spec)
		new_spec["encoding"]["detail"] = {"field": f, "type": "nominal"}
		if not is_broken_line_area_charts(new_spec, data):
			candidates.append(new_spec)
	return candidates


def try_repair_visualization(spec, data):
	"""given a spec and a data, try to repair it"""
	if "layer" in spec:
		layers = []
		for layer_spec, layer_data in break_down_layered(spec, data):
			if is_broken_line_area_charts(layer_spec, layer_data):
				repairs = repair_broken_line_area_chart(layer_spec, layer_data)
				if len(repairs) == 0:
					return None
				layers.append(repairs[0])
			else:
				layers.append(layer_spec)
		final_sepc = { "layer": layers }
	else:
		if is_broken_line_area_charts(spec, data):
			repairs = repair_broken_line_area_chart(spec, data)
			if len(repairs) == 0:
				return None
			final_sepc = repairs[0]
		else:
			final_sepc = spec
	return final_sepc


def infer_width_height(spec, data):
	"""given spec and data, infer the default height and width of the chart
	Returns: (width, height) pair indicate the spec size"""

	def infer_axis_attr(layer_spec, layer_data, axis):
		""" return type and properties of the axis"""
		if axis not in layer_spec["encoding"]:
			return None, None
		if layer_spec["encoding"][axis]["type"] == "nominal":
			return "discrete", list(set([r[layer_spec["encoding"][axis]["field"]] for r in layer_data]))
		else:
			return "continuous", None

	x_ty, x_values = [], []
	y_ty, y_values = [], []
	col_ty, col_values = [], []

	if "layer" in spec:	
		for layer_spec, layer_data in break_down_layered(spec, data):
			ty, vals = infer_axis_attr(layer_spec, layer_data, "x")
			x_ty.append(ty)
			if vals is not None:
				x_values += vals

			ty, vals = infer_axis_attr(layer_spec, layer_data, "y")
			y_ty.append(ty)
			if vals is not None:
				y_values += vals

			ty, vals = infer_axis_attr(layer_spec, layer_data, "column")
			col_ty.append(ty)
			if vals is not None:
				col_values += vals
	else:
		x_ty, x_values = infer_axis_attr(spec, data, "x")
		y_ty, y_values = infer_axis_attr(spec, data, "y")
		col_ty, col_values = infer_axis_attr(spec, data, "column")

		x_ty, y_ty, col_ty = [x_ty], [y_ty], [col_ty]

	unit_width = 20
	unit_height = 20
	cont_width = 200
	cont_height = 200
	width = 20
	height = 20

	if "discrete" in col_ty:
		if "discrete" in x_ty and len(set(x_values)) * len(set(col_values)) > 20:
			unit_width = 10
			unit_height = 10
		if "continuous" in x_ty and 200 * len(set(col_values)) > 600:
			cont_width = 80
			cont_height = 80


	if "discrete" in x_ty:
		if len(set(x_values)) * unit_width > 800:
			unit_width = 10
		width = unit_width * len(set(x_values))
	if "continuous" in x_ty:
		width = max(width, cont_width)

	
	if "discrete" in y_ty:
		if len(set(y_values)) * unit_height > 800:
			unit_height = 10
		height = unit_height * len(set(y_values))
	if "continuous" in y_ty:
		height = max(height, cont_width)

	return (width, height)


def update_encoding_type(spec, data):
	"""update encoding types based on data values"""

	def _update_encoding_type(layer_spec, layer_data):
		"""use side effect to update encodings"""
		mark = layer_spec["mark"]["type"] if isinstance(layer_spec["mark"], (dict,)) else layer_spec["mark"]
		if "color" in layer_spec["encoding"]:
			field_data = set([r[layer_spec["encoding"]["color"]["field"]] for r in layer_data])
			dtype = table_utils.infer_dtype(field_data)
			enc_ty = "nominal" if dtype == "string" else "quantitative"
			layer_spec["encoding"]["color"]["type"] = enc_ty
		if mark == "rect":
			for ch in layer_spec["encoding"]:
				if ch in ["x", "y"]:
					if layer_spec["encoding"][ch]["type"] != "nominal":
						layer_spec["encoding"][ch]["type"] = "nominal"

	if "layer" in spec:
		for layer_spec, layer_data in break_down_layered(spec, data):
			_update_encoding_type(layer_spec, layer_data)
	else:
		_update_encoding_type(spec, data)


def handle_scale_zero(spec, data):
	"""decide for continuous  visualization with zero """

	def _handle_scale_zero(layer_spec, layer_data):
		"""use side effect to update encodings"""
		mark = layer_spec["mark"]["type"] if isinstance(layer_spec["mark"], (dict,)) else layer_spec["mark"]
		for ch in ["x", "y"]:
			if ch in layer_spec["encoding"] and layer_spec["encoding"][ch]["type"] == "quantitative":
				field_data = [float(r[layer_spec["encoding"][ch]["field"]]) for r in layer_data]

				# don't use zero if the difference is too small
				if (max(field_data) - min(field_data)) * 5 < (min(field_data) - 0) or min(field_data) < 0:
					layer_spec["encoding"][ch]["scale"] = {"zero": None}

	if "layer" in spec:
		for layer_spec, layer_data in break_down_layered(spec, data):
			_handle_scale_zero(layer_spec, layer_data)
	else:
		_handle_scale_zero(spec, data)


def post_process_spec(spec, data):
	"""post process the visualization spec"""
	spec = try_repair_visualization(spec, data)
	update_encoding_type(spec, data)

	if spec is None:
		return None
	width, height = infer_width_height(spec, data)
	spec["width"] = width
	spec["height"] = height
	
	handle_scale_zero(spec, data)
	return spec


if __name__ == '__main__':

	data = [{"Quarter":"Quarter1","KEY":"Number of Units","VALUE":23,"layer_id":0},
			{"Quarter":"Quarter2","KEY":"Number of Units","VALUE":27,"layer_id":0},
			{"Quarter":"Quarter3","KEY":"Number of Units","VALUE":15,"layer_id":0},
			{"Quarter":"Quarter4","KEY":"Number of Units","VALUE":43,"layer_id":0},
			{"Quarter":"Quarter1","KEY":"Actual Profits","VALUE":3358,"layer_id":0},
			{"Quarter":"Quarter2","KEY":"Actual Profits","VALUE":3829,"layer_id":0},
			{"Quarter":"Quarter3","KEY":"Actual Profits","VALUE":2374,"layer_id":0},
			{"Quarter":"Quarter4","KEY":"Actual Profits","VALUE":3373,"layer_id":0},
			{"Quarter":"Quarter1","KEY":"Number of Units","VALUE":23,"layer_id":1},
			{"Quarter":"Quarter2","KEY":"Number of Units","VALUE":27,"layer_id":1},
			{"Quarter":"Quarter3","KEY":"Number of Units","VALUE":15,"layer_id":1},
			{"Quarter":"Quarter4","KEY":"Number of Units","VALUE":43,"layer_id":1},
			{"Quarter":"Quarter1","KEY":"Actual Profits","VALUE":3358,"layer_id":1},
			{"Quarter":"Quarter2","KEY":"Actual Profits","VALUE":3829,"layer_id":1},
			{"Quarter":"Quarter3","KEY":"Actual Profits","VALUE":2374,"layer_id":1},
			{"Quarter":"Quarter4","KEY":"Actual Profits","VALUE":3373,"layer_id":1}]

	spec = {
	  "layer": [
	    {
	      "mark": {"type": "bar", "opacity": 0.7},
	      "encoding": {
	        "x": {"field": "Quarter", "type": "nominal", "sort": None},
	        "y": {"field": "VALUE", "type": "quantitative"},
	        "color": {"field": "VALUE", "type": "quantitative"}
	      },
	      "transform": [{"filter": "datum.layer_id == 0"}]
	    },
	    {
	      "mark": {"type": "line", "opacity": 0.7},
	      "encoding": {
	        "x": {"field": "Quarter", "type": "nominal"},
	        "y": {"field": "VALUE", "type": "quantitative"},
	        "order": {"field": "Quarter", "type": "quantitative"}
	      },
	      "transform": [{"filter": "datum.layer_id == 1"}]
	    }
	  ]
	}


	spec = post_process_spec(spec, data)
	spec["data"] = {"values": data}

	print(json.dumps(spec))





