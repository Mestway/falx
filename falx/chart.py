from collections import namedtuple
import json
import copy


Rect = namedtuple("Rect", ["x", "y", "color", "width", "height", "chart_id", "group"])
Point = namedtuple("Point", ["shape", "x", "y", "size", "color", "chart_id", "group"])
Line = namedtuple("Line", ["x", "y", "x_delta", "y_delta", "size", "chart_id", "group"])
Area = namedtuple("Area", ["x", "y", "color", "chart_id", "group"])

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
		vl_obj = {
			"mark": "bar",
			"encoding": {e.channel:e.to_vl_obj() for e in self.encodings}
		}
		vl_obj["encoding"]["column"] = enc_group.to_vl_obj()
		return vl_obj

	def eval(self, data):
		grouped_data = {}
		group_vals = []
		# TODO
		pass


class LayeredChart(object):
	def __init__(self, layers, shared_encodings, resolve):
		"""A layered bar chart where  """
		self.layers = layers
		self.shared_encodings = shared_encodings
		self.resolve = resolve

	def to_vl_obj(self):
		layer_obj = [l.to_vl_obj() for l in self.layers]
		for l in layer_obj:
			l["mark"] = {"type": l["mark"], "opacity": 0.7}
		vl_obj = {
			"encoding": {e.channel:e.to_vl_obj() for e in self.shared_encodings},
			"layer": layer_obj,
			"resolve": self.resolve
		}
		return vl_obj

	def eval(self, data):
		result = []
		for layer in self.layers:
			inst_layer = copy.copy(layer)
			inst_layer.encodings.extend(self.shared_encodings)
			result += inst_layer.eval(data)
		return result

class BarChart(object):
	def __init__(self, encodings):
		"""encodings of x,y,x2,y2"""
		self.encodings = encodings

	def to_vl_obj(self):
		return {
			"mark": "bar",
			"encoding": {e.channel:e.to_vl_obj() for e in self.encodings}
		}

class StackedChart(object):
	def __init__(self, chart_ty, stack_channel, stack_ty, encodings):
		""" encodings x,y,x2,y2,color"""
		self.chart_ty = chart_ty
		self.stack_channel = stack_channel
		self.stack_ty = stack_ty
		self.encodings = encodings

	def to_vl_obj(self):
		vl_obj = {
			"mark": self.chart_ty,
			"encoding": {e.channel:e.to_vl_obj() for e in self.encodings}
		}
		vl_obj["encoding"][self.stack_channel]["stack"] = self.stack_ty
		return vl_obj

class LineChart(object):
	def __init__(self, encodings):
		"""Encodings x,y,color,size"""
		self.encodings = encodings

	def to_vl_obj(self):
		return {
			"mark": "line",
			"encoding": {e.channel:e.to_vl_obj() for e in self.encodings}
		}

class ScatterPlot(object):
	def __init__(self, mark_ty, encodings):
		"""enc_x, enc_y, enc_color, enc_size, enc_shape"""
		self.mark_ty = mark_ty
		self.encodings = encodings

	def to_vl_obj(self):
		return {
			"mark": self.mark_ty,
			"encoding": {e.channel:e.to_vl_obj() for e in self.encodings}
		}

class Encoding(object):
	def __init__(self, channel, field, enc_ty, sort_ty=None):
		self.channel = channel
		self.field = field
		self.enc_ty = enc_ty
		self.sort_ty = sort_ty

	def to_vl_obj(self):
		res = {"field": self.field, "type": self.enc_ty}
		if self.sort_ty:
			res["sort_ty"] = self.sort_ty
		return res
