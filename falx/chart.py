import json
import copy
from pprint import pprint

from namedlist import namedlist

# mutatable
Rect = namedlist("Rect", ["x", "y", "color", "width", "height", "group"], default=None)
Point = namedlist("Point", ["shape", "x", "y", "size", "color", "group"], default=None)
Line = namedlist("Line", ["x1", "y1", "x2", "y2", "size", "color", "group"], default=None)
Area = namedlist("Area", ["x", "y", "color", "group"])

get_x = lambda encs, r: sorted((r[encs["x"].field], r[encs["x2"].field])) if "x2" in encs else r[encs["x"].field]
get_y = lambda encs, r: sorted((r[encs["y"].field], r[encs["y2"].field])) if "y2" in encs else r[encs["y"].field]
get_channel = lambda encs, channel, r: r[encs[channel].field] if channel in encs else None

class VisDesign(object):
	"""Top level visualization construct """
	def __init__(self, data, chart):
		self.data = data
		self.chart = chart

	def to_vl_obj(self):
		chart_obj = self.chart.to_vl_obj()
		chart_obj["data"] = {"values": self.data}
		return chart_obj

	def to_vl_json(self):
		return json.dumps(self.to_vl_obj())

	def eval(self):
		return self.chart.eval(self.data)

class GroupChart(object):
	"""Repeat the chart for multiple groups """
	def __init__(self, enc_group, layer):
		self.layer = layer
		self.enc_group = enc_group

	def to_vl_obj(self):
		vl_obj = self.layer.to_vl_obj()
		vl_obj["encoding"]["column"] = self.enc_group.to_vl_obj()
		return vl_obj

	def eval(self, data):
		"""group data based on the group column and then evaluate each group"""
		group_keys = set([r[self.enc_group.field] for r in data])
		grouped_data = {g:[r for r in data if r[self.enc_group.field] == g] for g in group_keys}
		components = {g:self.layer.eval(grouped_data[g]) for g in grouped_data}
		result = []
		for g in components:
			for d in components[g]:
				d.group = g
			result += components[g]
		return result

class LayeredChart(object):
	def __init__(self, layers, shared_encodings, resolve):
		"""A layered chart, shared encodings contains encodings for all layers. """
		self.layers = layers
		self.shared_encodings = {e.channel:e for e in shared_encodings}
		self.resolve = resolve

	def to_vl_obj(self):
		layer_obj = [l.to_vl_obj() for l in self.layers]
		for l in layer_obj:
			l["mark"] = {"type": l["mark"], "opacity": 0.7}
		vl_obj = {
			"encoding": {e:self.shared_encodings[e].to_vl_obj() for e in self.shared_encodings},
			"layer": layer_obj,
			"resolve": self.resolve
		}
		return vl_obj

	def eval(self, data):
		"""obtain elements in each layer and put them together. """
		result = []
		for layer in self.layers:
			inst_layer = copy.copy(layer)
			for e in self.shared_encodings:
				inst_layer.encodings[e] = self.shared_encodings[e]
			result += inst_layer.eval(data)
		return result

class BarChart(object):
	def __init__(self, encodings, orientation):
		"""encodings of x,y,x2,y2
			orientation is one of vertical / horizontal
		"""
		self.encodings = {e.channel:e for e in encodings}
		self.orientation = orientation

	def to_vl_obj(self):
		return {
			"mark": "bar",
			"encoding": {e:self.encodings[e].to_vl_obj() for e in self.encodings}
		}

	def eval(self, data):
		res = []
		for r in data:
			x = get_x(self.encodings, r)
			y = get_y(self.encodings, r)
			width = (x[1] - x[0]) if isinstance(x, (tuple, list,)) else (x if self.orientation == "horizontal" else 1)
			height = (y[1] - y[0]) if isinstance(y, (tuple, list,)) else (y if self.orientation == "vertical" else 1)
			res.append(Rect(x=x, y=y, width=width, height=height))
		return res

class StackedChart(object):
	def __init__(self, chart_ty, stack_channel, stack_ty, encodings):
		""" encodings x,y,color
			stack_channel, stack_ty: specifies which channel to stack and the stack configuration
		"""
		self.chart_ty = chart_ty
		self.stack_channel = stack_channel
		self.stack_position = "y" if stack_channel == "x" else "x"
		self.stack_ty = stack_ty
		self.encodings = {e.channel:e for e in encodings}

	def to_vl_obj(self):
		vl_obj = {
			"mark": self.chart_ty,
			"encoding": {e:self.encodings[e].to_vl_obj() for e in self.encodings}
		}
		vl_obj["encoding"][self.stack_channel]["stack"] = self.stack_ty
		return vl_obj

	def eval(self, data):
		"""first group data based on stack channel and then stack them """								   
		group_keys = set([r[self.encodings[self.stack_position].field] for r in data])
		grouped_data = {key: [r for r in data if r[self.encodings[self.stack_position].field] == key] for key in group_keys}
		stack_order = self.encodings["color"].sort_order

		res = []
		for key in grouped_data:
			vals = grouped_data[key]
			vals.sort(key=lambda x: x[self.encodings["color"].field], 
					  reverse=True if stack_order == 'descending' else False)

			# only used when there is no interval value for x, y
			last_stack_val = 0
			for r in vals:
				x = get_channel(self.encodings, "x", r)
				y = get_channel(self.encodings, "y", r)

				if self.stack_channel == "y" and not isinstance(y, (tuple, list,)):
					y = (last_stack_val, last_stack_val + y)
					last_stack_val = y[1]

				if self.stack_channel == "x" and not isinstance(x, (tuple, list,)):
					x = (last_stack_val, last_stack_val + x)
					last_stack_val = x[1]

				width = (x[1] - x[0]) if isinstance(x, (tuple, list,)) else (x if self.encodings["x"].enc_ty == "quantitative" else 1)
				height = (y[1] - y[0]) if isinstance(y, (tuple, list,)) else (y if self.encodings["y"].enc_ty == "quantitative" else 1)
				color = get_channel(self.encodings, "color", r)
				res.append(Rect(x=x, y=y, color=color, width=width, height=height))

		return res

class LineChart(object):
	def __init__(self, encodings):
		"""Encodings x,y,color,size,order"""
		self.encodings = {e.channel:e for e in encodings}
		if "order" not in self.encodings:
			# the default order to connect points is based on x encoding
			self.encodings["order"] = self.encodings["x"]

	def to_vl_obj(self):
		return {
			"mark": "line",
			"encoding": {e:self.encodings[e].to_vl_obj() for e in self.encodings}
		}

	def eval(self, data):
		""" first group data based on color and width, and then connect them"""
		get_group_key = lambda r: (r[self.encodings["color"].field] if "color" in self.encodings else None,
								   r[self.encodings["size"].field] if "size" in self.encodings else None)
		group_keys = set([get_group_key(r) for r in data])
		grouped_data = {key:[r for r in data if get_group_key(r) == key] for key in group_keys}

		res = []
		for key in grouped_data:
			vals = grouped_data[key]
			order_channel = self.encodings["order"].channel
			sort_order = self.encodings["order"].sort_order
			if sort_order != None:
				vals.sort(key=lambda x: x[order_channel], reverse=True if sort_order == "descending" else False)

			color, size = key
			for i in range(len(vals) - 1):
				l, r = vals[i], vals[i + 1]
				xl, yl = l[self.encodings["x"].field], l[self.encodings["y"].field]
				xr, yr = r[self.encodings["x"].field], r[self.encodings["y"].field]
				res.append(Line(xl, yl, xr, yr, size, color))

		return res

class ScatterPlot(object):
	def __init__(self, mark_ty, encodings):
		"""x, y, color, size, shape"""
		self.mark_ty = mark_ty
		self.encodings = {e.channel:e for e in encodings}

	def to_vl_obj(self):
		return {
			"mark": self.mark_ty,
			"encoding": {e:self.encodings[e].to_vl_obj() for e in self.encodings}
		}

	def eval(self, data):
		res = []
		for r in data:
			x = get_channel(self.encodings, "x", r)
			y = get_channel(self.encodings, "y", r)
			color = get_channel(self.encodings, "color", r)
			size = get_channel(self.encodings, "size", r)
			shape = get_channel(self.encodings, "shape", r)
			res.append(Point(x=x, y=y, color=color, size=size, shape=shape))
		return res

class Encoding(object):
	def __init__(self, channel, field, enc_ty, sort_order=None):
		""" sort order is either descending/ascending or default (unsorted)"""
		self.channel = channel
		self.field = field
		self.enc_ty = enc_ty
		self.sort_order = sort_order

	def to_vl_obj(self):
		res = {"field": self.field, "type": self.enc_ty}
		if self.sort_order:
			res["sort_order"] = self.sort_order
		return res
