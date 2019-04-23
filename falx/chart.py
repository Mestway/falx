import json
import copy
from pprint import pprint

from namedlist import namedlist

# mutatable vtrace
BarV = namedlist("BarV", ["x", "y1", "y2", "color", "group"], default=None)
BarH = namedlist("BarH", ["x1", "x2", "y", "color", "group"], default=None)
Point = namedlist("Point", ["shape", "x", "y", "size", "color", "group"], default=None)
Line = namedlist("Line", ["x1", "y1", "x2", "y2", "size", "color", "group"], default=None)
Area = namedlist("Area", ["x", "y", "color", "group"])

def get_vt_type(v):
	return type(v).__name__

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

	@staticmethod
	def inv_eval(vtrace):
		# partition trace elements by types
		trace_layer = {}
		for v in vtrace:
			vty = get_vt_type(v)
			if vty not in trace_layer:
				trace_layer[vty] = []
			trace_layer[vty].append(v)

		pprint(trace_layer)
		
		layers = {}
		for vty in trace_layer:
			if vty == "BarV":
				l1 = BarChart.inv_eval(trace_layer[vty], orientation="vertical")
				l2 = StackedChart.inv_eval(trace_layer[vty], orientation="vertical")
				layers[vty] = l1 + l2
			elif vty == "BarH":
				l1 = BarChart.inv_eval(trace_layer[vty], orientation="horizontal")
				l2 = StackedChart.inv_eval(trace_layer[vty], orientation="horizontal")
				layers[vty] = l1 + l2
			elif vty == "Point":
				layers[vty] = ScatterPlot.inv_eval(trace_layer[vty])
			elif vty == "Line":
				layers[vty] = LineChart.inv_eval(trace_layer[vty])
			elif vty == "Area":
				#TODO: handle area chart later
				pass

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
			if self.orientation == "horizontal":
				x1 = get_channel(self.encodings, "x", r)
				x2 = get_channel(self.encodings, "x2", r)
				y = get_channel(self.encodings, "y", r)
				res.append(BarH(x1=x1, x2=x2, y=y))
			elif self.orientation == "vertical":
				y1 = get_channel(self.encodings, "y", r)
				y2 = get_channel(self.encodings, "y2", r)
				x = get_channel(self.encodings, "x", r)
				res.append(BarV(x=x, y1=y1, y2=y2))
		return res

	@staticmethod
	def inv_eval(vtrace, orientation):
		#TODO
		return []

class StackedChart(object):
	def __init__(self, chart_ty, orientation, encodings):
		""" encodings x,y,color
			stack_channel, stack_ty: specifies which channel to stack and the stack configuration
		"""
		self.chart_ty = chart_ty
		self.orientation = orientation
		self.encodings = {e.channel:e for e in encodings}

	def to_vl_obj(self):
		vl_obj = {
			"mark": self.chart_ty,
			"encoding": {e:self.encodings[e].to_vl_obj() for e in self.encodings}
		}
		return vl_obj

	def eval(self, data):
		"""first group data based on stack channel and then stack them """	
		stack_pos = "x" if self.orientation == "vertical" else "y"

		# group based on stack_pos channel
		group_keys = set([r[self.encodings[stack_pos].field] for r in data])
		grouped_data = {key: [r for r in data if r[self.encodings[stack_pos].field] == key] for key in group_keys}
		stack_order = self.encodings["color"].sort_order

		res = []
		for key in grouped_data:
			vals = grouped_data[key]
			vals.sort(key=lambda x: x[self.encodings["color"].field], 
					  reverse=False if stack_order == 'ascending' else True)

			# only used when there is no interval value for x, y
			last_stack_val = 0
			for r in vals:
				x = get_channel(self.encodings, "x", r)
				y = get_channel(self.encodings, "y", r)
				color = get_channel(self.encodings, "color", r)

				if self.orientation == "vertical":
					y = (last_stack_val, last_stack_val + y)
					last_stack_val = y[1]
					res.append(BarV(x=x, y1=y[0], y2=y[1], color=color))

				if self.orientation == "horizontal":
					x = (last_stack_val, last_stack_val + x)
					last_stack_val = x[1]
					res.append(BarH(x1=x[0], x2=x[0], y=y, color=color))

		return res

	@staticmethod
	def inv_eval(vtrace, orientation):
		#TODO
		return []

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

	@staticmethod
	def inv_eval(vtrace):
		#TODO
		return []

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

	@staticmethod
	def inv_eval(vtrace):
		#TODO
		return []

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