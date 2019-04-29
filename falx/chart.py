import json
import copy
from pprint import pprint

import itertools
from namedlist import namedlist
import numpy as np

from abstract_table import AbstractTable
import utils

# mutatable vtrace
BarV = namedlist("BarV", ["x", "y1", "y2", "color", "column"], default=None)
BarH = namedlist("BarH", ["x1", "x2", "y", "color", "column"], default=None)
Point = namedlist("Point", ["shape", "x", "y", "size", "color", "column"], default=None)
Line = namedlist("Line", ["x1", "y1", "x2", "y2", "size", "color", "column"], default=None)
Area = namedlist("Area", ["x1", "yt1", "yb1", "x2", "yt2", "yb2", "color", "column"], default=None)
Box = namedlist("Box", ["x", "min", "max", "Q1", "median", "Q3", "color", "column"], default=None)

def get_vt_type(v):
    return type(v).__name__

def remove_unused_fields(data):
    # remove fields that contain none values
    unused_fields = [key for key in data[0] if any([r[key] is None for r in data])]
    for r in data:
        for k in unused_fields:
            r.pop(k)
    return unused_fields

get_channel = lambda encs, channel, r: r[encs[channel].field] if channel in encs else None

class VisDesign(object):
    """Top level visualization construct """
    def __init__(self, data, chart):
        # data can either be a table list (for layered chart) or a single table
        self.data = data
        self.chart = chart

    def to_vl_obj(self):
        chart_obj = self.chart.to_vl_obj()
        if isinstance(self.data[0], (list,)):
            # this case represents a data list for layered chart
            combined_data = []
            for i, layer_data in enumerate(self.data):
                for r in layer_data:
                    new_r = copy.copy(r)
                    new_r["layer_id"] = i
                    combined_data.append(new_r)

            chart_obj["data"] = {"values": combined_data}
        else:
            chart_obj["data"] = {"values": self.data}

        return chart_obj

    def to_vl_json(self):
        return json.dumps(self.to_vl_obj())

    def eval(self):
        return self.chart.eval(self.data)

    @staticmethod
    def inv_eval(vtrace):
        """inverse evaluation of a visual trace 
        Args: vtrace: a visual trace
        Returns: a list of pairs (abs_table, vis) s.t. vis(abs_table)=vtrace
        """
        res = []
        for abs_table, chart in LayeredChart.inv_eval(vtrace):
            res.append(VisDesign(abs_table, chart).to_vl_json())
        return res


class LayeredChart(object):
    def __init__(self, layers, resolve):
        """A layered chart, shared encodings contains encodings for all layers. """
        self.layers = layers
        self.resolve = resolve

    def to_vl_obj(self):
        layer_obj = [l.to_vl_obj() for l in self.layers]
        for i, l in enumerate(layer_obj):
            if isinstance(l["mark"], (dict,)) and "opacity" in l["mark"]:
                # opacity for the given chart is already set
                l["mark"]["opacity"] = 0.7
            else:
                l["mark"] = {"type": l["mark"], "opacity": 0.7}
            l["transform"] = [{"filter": "datum.layer_id == {}".format(i)}]
        vl_obj = {
            "layer": layer_obj,
            "resolve": self.resolve
        }
        return vl_obj

    def to_vl_json(self):
        return json.dumps(self.to_vl_obj())

    def eval(self, data_list):
        """obtain elements in each layer and put them together. """
        result = []
        for data, layer in zip(data_list, self.layers):
            result += layer.eval(data)
        return result

    @staticmethod
    def inv_eval(vtrace):
        """returns a list of (abs_table, layer) pairs. """
        trace_layer = {}
        for v in vtrace:
            vty = get_vt_type(v)
            if vty not in trace_layer:
                trace_layer[vty] = []
            trace_layer[vty].append(v)
        
        layers = {}
        for vty in trace_layer:
            if vty == "BarV":
                l1 = BarChart.inv_eval(trace_layer[vty], orientation="vertical")
                l2 = StackedBarChart.inv_eval(trace_layer[vty], orientation="vertical")
                layers[vty] = l1 + l2
            elif vty == "BarH":
                l1 = BarChart.inv_eval(trace_layer[vty], orientation="horizontal")
                l2 = StackedBarChart.inv_eval(trace_layer[vty], orientation="horizontal")
                layers[vty] = l1 + l2
            elif vty == "Point":
                layers[vty] = ScatterPlot.inv_eval(trace_layer[vty])
            elif vty == "Line":
                layers[vty] = LineChart.inv_eval(trace_layer[vty])
            elif vty == "Area":
                layers[vty] = AreaChart.inv_eval(trace_layer[vty])
            elif vty == "Box":
                layers[vty] = BoxPlot.inv_eval(trace_layer[vty])
                #TODO: handle stacked area chart later

        if len(layers) == 1:
            # directly return the layer if there is only one layer
            return layers[list(layers.keys())[0]]
        else:
            res = []
            layer_candidates = [layers[vty] for vty in layers]
            sizes = [list(range(len(l))) for l in layer_candidates]
            
            # iterating over combinations for different layers
            for id_list in itertools.product(*sizes):
                #id_list[i] is the candidate (data, layer) pair for layer i
                data_layer_pairs = [layer_candidates[i][id_list[i]] for i in range(len(id_list))]
                data_list = [cl[0] for cl in data_layer_pairs]
                chart_layers = [cl[1] for cl in data_layer_pairs]
                res.append((data_list, LayeredChart(layers=chart_layers, resolve={})))
            return  res 


class BarChart(object):
    def __init__(self, encodings, orientation):
        """encodings of x,y,x2,y2
            orientation is one of vertical / horizontal
        """
        assert(orientation in ["horizontal", "vertical"])
        self.encodings = {e.channel:e for e in encodings}
        self.orientation = orientation

    def to_vl_obj(self):
        mark = "bar"
        encodings =  {e:self.encodings[e].to_vl_obj() for e in self.encodings}
        if "color" in self.encodings:
            mark = {"type": "bar", "opacity": 0.8}
            if self.orientation == "horizontal":
                encodings["x"]["stack"] = None
            if self.orientation == "vertical":
                encodings["y"]["stack"] = None
        return {
            "mark": mark,
            "encoding": encodings
        }

    def to_vl_json(self):
        return json.dumps(self.to_vl_obj())

    def eval(self, data):
        res = []
        for r in data:
            if self.orientation == "horizontal":
                x1 = get_channel(self.encodings, "x", r)
                x2 = get_channel(self.encodings, "x2", r)
                y = get_channel(self.encodings, "y", r)
                color = get_channel(self.encodings, "color", r)
                column = get_channel(self.encodings, "column", r)
                res.append(BarH(x1=x1, x2=x2, y=y, color=color, column=column))
            elif self.orientation == "vertical":
                y1 = get_channel(self.encodings, "y", r)
                y2 = get_channel(self.encodings, "y2", r)
                x = get_channel(self.encodings, "x", r)
                color = get_channel(self.encodings, "color", r)
                column = get_channel(self.encodings, "column", r)
                res.append(BarV(x=x, y1=y1, y2=y2, color=color, column=column))
        return res

    @staticmethod
    def inv_eval(vtrace, orientation):
        data = []

        assert(orientation in ["horizontal", "vertical"])
        
        if orientation == "vertical":
            for vt in vtrace:
                data.append({"c_x": vt.x, "c_y": vt.y1, "c_y2": vt.y2, "c_column": vt.column, "c_color": vt.color})
            channel_types = [("x", "nominal"), ("y", "quantitative"), ("y2", "quantitative"), ("color", "nominal"), ("column", "nominal")]
       
        if orientation == "horizontal":
            for vt in vtrace:
                data.append({"c_x": vt.x1, "c_x2": vt.x2, "c_y": vt.y, "c_column": vt.column, "c_color": vt.color})
            channel_types = [("x", "quantitative"), ("x2", "quantitative"), ("y", "nominal"), ("color", "nominal"), ("column", "nominal")]
        
        # remove fields that contain none values
        unused_fields = remove_unused_fields(data)

        encodings = []
        for channel, enc_ty in channel_types:
            field_name = "c_{}".format(channel)
            if field_name in unused_fields:
                continue
            encodings.append(Encoding(channel, field_name, enc_ty))

        bar_chart = BarChart(encodings=encodings, orientation=orientation)

        return [(data, bar_chart)]


class StackedBarChart(object):
    def __init__(self, orientation, encodings):
        """ encodings x,y,color
            stack_channel, stack_ty: specifies which channel to stack and the stack configuration
        """
        assert(orientation in ["horizontal", "vertical"])
        self.orientation = orientation
        self.encodings = {e.channel:e for e in encodings}

    def to_vl_obj(self):
        vl_obj = {
            "mark": "bar",
            "encoding": {e:self.encodings[e].to_vl_obj() for e in self.encodings}
        }
        return vl_obj

    def to_vl_json(self):
        return json.dumps(self.to_vl_obj())

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
                column = get_channel(self.encodings, "column", r)

                if self.orientation == "vertical":
                    y = (last_stack_val, last_stack_val + y)
                    last_stack_val = y[1]
                    res.append(BarV(x=x, y1=y[0], y2=y[1], color=color, column=column))

                if self.orientation == "horizontal":
                    x = (last_stack_val, last_stack_val + x)
                    last_stack_val = x[1]
                    res.append(BarH(x1=x[0], x2=x[0], y=y, color=color, column=column))
        return res

    @staticmethod
    def inv_eval(vtrace, orientation):

        assert(orientation in ["horizontal", "vertical"])

        """inverse construction of vertical bars """
        if ((orientation=="horizontal" and any([vt.x1 is None or vt.x2 is None for vt in vtrace]))
            or (orientation=="vertical" and any([vt.y1 is None or vt.y2 is None for vt in vtrace]))):
                # it does not satisfy stacked bar semantics
                return []
        
        data = []
        if orientation == "vertical":
            # vertical stacked bar
            for vt in vtrace:
                data.append({"c_x": vt.x, "c_y": vt.y2 - vt.y1, "c_color": vt.color, "c_column": vt.column})
            channel_types = [("x", "nominal"), ("y", "quantitative"), ("color", "nominal"), ("column", "nominal")]
        elif orientation == "horizontal":
            # horizontal stacked bar
            for vt in vtrace:
                data.append({"c_x": vt.x2 - vt.x1, "c_y": vt.y, "c_color": vt.color, "c_column": vt.column})
            channel_types = [("x", "quantitative"), ("y", "nominal"), ("color", "nominal"), ("column", "nominal")]

        # remove fields that contain none values
        unused_fields = remove_unused_fields(data)

        encodings = []
        for channel, enc_ty in channel_types:
            field_name = "c_{}".format(channel)
            if field_name in unused_fields:
                continue
            encodings.append(Encoding(channel, field_name, enc_ty))

        bar_chart = StackedBarChart(encodings=encodings, orientation=orientation)
        return [(data, bar_chart)]


class BoxPlot(object):
    def __init__(self, encodings):
        """ encodes x, y, color, group"""
        self.encodings = {e.channel:e for e in encodings}

    def to_vl_obj(self):
        mark = { "type": "boxplot", "extent": "min-max" }
        encodings =  {e:self.encodings[e].to_vl_obj() for e in self.encodings}
        return {
            "mark": mark,
            "encoding": encodings
        }

    def to_vl_json(self):
        return json.dumps(self.to_vl_obj())

    def eval(self, data):
        res = []
        # group by x, color and column to generate a box for each item
        get_group_key = lambda r: (r[self.encodings["x"].field] if "x" in self.encodings else None,
                                   r[self.encodings["color"].field] if "color" in self.encodings else None,
                                   r[self.encodings["column"].field] if "column" in self.encodings else None)
        group_keys = set([get_group_key(r) for r in data])
        grouped_data = {key:[r for r in data if get_group_key(r) == key] for key in group_keys}

        for key in grouped_data:
            x, color, column = key
            ys = [r[self.encodings["y"].field] for r in grouped_data[key]]
            median = float(np.median(ys))
            upper_quartile = float(np.percentile(ys, 75))
            lower_quartile = float(np.percentile(ys, 25))
            res.append(Box(x=x, median=median, Q1=lower_quartile, Q3=upper_quartile, 
                           min=float(np.min(ys)), max=float(np.max(ys)), color=color, column=column))
        return res

    @staticmethod
    def inv_eval(vtrace):
        data = []
        for vt in vtrace:
            data.append({"c_x": vt.x, "c_y": vt.Q1, "c_color": vt.color,  "c_column": vt.column})
            data.append({"c_x": vt.x, "c_y": vt.Q3, "c_color": vt.color,  "c_column": vt.column})
            data.append({"c_x": vt.x, "c_y": vt.median, "c_color": vt.color,  "c_column": vt.column})
            data.append({"c_x": vt.x, "c_y": vt.min, "c_color": vt.color,  "c_column": vt.column})
            data.append({"c_x": vt.x, "c_y": vt.max, "c_color": vt.color,  "c_column": vt.column})

        # remove fields that contain none values
        unused_fields = remove_unused_fields(data)

        encodings = []
        for channel, enc_ty in [("x", "_"), ("y", "_"), ("color", "nominal"), ("column", "nominal")]:
            field_name = "c_{}".format(channel)
            if field_name in unused_fields: 
                continue

            if channel in ["x", "y"]:
                # the type needs to be determined by datatype
                dtype = utils.infer_dtype([r[field_name] for r in data])
                enc_ty = "nominal" if dtype == "string" else "quantitative"

            encodings.append(Encoding(channel, field_name, enc_ty))

        chart = BoxPlot(encodings=encodings)
        return [(data, chart)]


class AreaChart(object):
    def __init__(self, encodings):
        """encodings of x,y,y2,color """
        self.encodings = {e.channel:e for e in encodings}

    def to_vl_obj(self):
        mark = "area"
        encodings =  {e:self.encodings[e].to_vl_obj() for e in self.encodings}
        if "color" in self.encodings:
            mark = {"type": "area", "opacity": 0.8}
            encodings["y"]["stack"] = None
        return {
            "mark": mark,
            "encoding": encodings
        }

    def to_vl_json(self):
        return json.dumps(self.to_vl_obj())

    def eval(self, data):
        """ first group data based on color and column and then connect them"""
        get_group_key = lambda r: (r[self.encodings["color"].field] if "color" in self.encodings else None,
                                   r[self.encodings["column"].field] if "column" in self.encodings else None)
        group_keys = set([get_group_key(r) for r in data])
        grouped_data = {key:[r for r in data if get_group_key(r) == key] for key in group_keys}

        res = []
        for key in grouped_data:
            vals = grouped_data[key]
            # sort by ascending in x by default
            vals.sort(key=lambda x: x[self.encodings["x"].field])

            color, column = key
            for i in range(len(vals) - 1):
                l, r = vals[i], vals[i + 1]
                xl, ylt, ylb = l[self.encodings["x"].field], l[self.encodings["y"].field], get_channel(self.encodings, "y2", l)
                xr, yrt, yrb = r[self.encodings["x"].field], r[self.encodings["y"].field], get_channel(self.encodings, "y2", r)
                res.append(Area(xl, ylt, ylb, xr, yrt, yrb, color, column))
        return res

    @staticmethod
    def inv_eval(vtrace):

        frozen_data = []
        for vt in vtrace:
            # each end of an point will only be added once
            p1 = json.dumps({"c_x": vt.x1, "c_y": vt.yt1, "c_y2": vt.yb1, "c_color": vt.color, "c_column": vt.column}, sort_keys=True)
            p2 = json.dumps({"c_x": vt.x2, "c_y": vt.yt2, "c_y2": vt.yb2, "c_color": vt.color, "c_column": vt.column}, sort_keys=True)
            if p1 not in frozen_data: frozen_data.append(p1)
            if p2 not in frozen_data: frozen_data.append(p2)

        data = [json.loads(r) for r in frozen_data]
        channel_types = [("x", "_"), ("y", "quantitative"), ("y2", "quantitative"), ("color", "nominal"), ("column", "nominal")]

        # remove fields that contain none values
        unused_fields = remove_unused_fields(data)

        encodings = []
        for channel, enc_ty in channel_types:
            field_name = "c_{}".format(channel)
            if field_name in unused_fields:
                continue
            if channel == "x":
                dtype = utils.infer_dtype([r[field_name] for r in data])
                enc_ty = "nominal" if dtype == "string" else "quantitative"
            encodings.append(Encoding(channel, field_name, enc_ty))

        chart = AreaChart(encodings=encodings)

        return [(data, chart)]


class LineChart(object):
    def __init__(self, encodings):
        """Encodings x,y,color,size,order"""
        self.encodings = {e.channel:e for e in encodings}
        if "order" not in self.encodings:
            # the default order to connect points is based on x encoding
            self.encodings["order"] = Encoding(channel="order", field=self.encodings["x"].field, enc_ty="quantitative")

    def to_vl_obj(self):
        return {
            "mark": "line",
            "encoding": {e:self.encodings[e].to_vl_obj() for e in self.encodings}
        }

    def to_vl_json(self):
        return json.dumps(self.to_vl_obj())

    def eval(self, data):
        """ first group data based on color and width, and then connect them"""
        get_group_key = lambda r: (r[self.encodings["color"].field] if "color" in self.encodings else None,
                                   r[self.encodings["size"].field] if "size" in self.encodings else None,
                                   r[self.encodings["column"].field] if "column" in self.encodings else None)
        group_keys = set([get_group_key(r) for r in data])
        grouped_data = {key:[r for r in data if get_group_key(r) == key] for key in group_keys}

        res = []
        for key in grouped_data:
            vals = grouped_data[key]
            order_field = self.encodings["order"].field
            sort_order = self.encodings["order"].sort_order
            if sort_order != None:
                vals.sort(key=lambda x: x[order_field], reverse=True if sort_order == "descending" else False)

            color, size, column = key
            for i in range(len(vals) - 1):
                l, r = vals[i], vals[i + 1]
                xl, yl = l[self.encodings["x"].field], l[self.encodings["y"].field]
                xr, yr = r[self.encodings["x"].field], r[self.encodings["y"].field]
                res.append(Line(xl, yl, xr, yr, size, color, column))
        return res

    @staticmethod
    def inv_eval(vtrace):
        frozen_data = []
        for vt in vtrace:
            # each end of an point will only be added once
            p1 = json.dumps({"c_x": vt.x1, "c_y": vt.y1, "c_size": vt.size, "c_color": vt.color, "c_column": vt.column}, sort_keys=True)
            p2 = json.dumps({"c_x": vt.x2, "c_y": vt.y2, "c_size": vt.size, "c_color": vt.color, "c_column": vt.column}, sort_keys=True)
            if p1 not in frozen_data: frozen_data.append(p1)
            if p2 not in frozen_data: frozen_data.append(p2)
        
        data = [json.loads(r) for r in frozen_data]

        unused_fields = remove_unused_fields(data)

        encodings = []
        for channel, enc_ty in [("x", "_"), ("y", "_"), ("size", "nominal"), ("color", "nominal"), ("column", "nominal")]:
            field_name = "c_{}".format(channel)
            if field_name in unused_fields:
                continue
            if channel in ["x", "y"]:
                dtype = utils.infer_dtype([r[field_name] for r in data])
                enc_ty = "nominal" if dtype == "string" else "quantitative"

            encodings.append(Encoding(channel, field_name, enc_ty))

        bar_chart = LineChart(encodings=encodings)
        return [(data, bar_chart)]


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

    def to_vl_json(self):
        return json.dumps(self.to_vl_obj())

    def eval(self, data):
        res = []
        for r in data:
            x = get_channel(self.encodings, "x", r)
            y = get_channel(self.encodings, "y", r)
            color = get_channel(self.encodings, "color", r)
            size = get_channel(self.encodings, "size", r)
            shape = get_channel(self.encodings, "shape", r)
            column = get_channel(self.encodings, "column", r)
            res.append(Point(x=x, y=y, color=color, size=size, shape=shape, column=column))
        return res

    @staticmethod
    def inv_eval(vtrace):
        data = []
        for vt in vtrace:
            data.append({"c_x": vt.x, "c_y": vt.y, "c_size": vt.size, 
                         "c_color": vt.color, "c_shape": vt.shape, "c_column": vt.column})

        # remove fields that contain none values
        unused_fields = remove_unused_fields(data)

        encodings = []
        for channel, enc_ty in [("x", "_"), ("y", "_"), 
                                ("size", "_"), ("color", "nominal"), ("shape", "nominal"), ("column", "nominal")]:
            field_name = "c_{}".format(channel)
            if field_name in unused_fields: 
                continue

            if channel in ["x", "y", "size"]:
                # the type needs to be determined by datatype
                dtype = utils.infer_dtype([r[field_name] for r in data])
                enc_ty = "nominal" if dtype == "string" else "quantitative"

            encodings.append(Encoding(channel, field_name, enc_ty))

        bar_chart = ScatterPlot(mark_ty="point", encodings=encodings)
        return [(data, bar_chart)]


class Encoding(object):
    def __init__(self, channel, field, enc_ty, sort_order=None):
        """ sort order is either descending/ascending or default (unsorted)"""
        self.channel = channel
        self.field = field
        self.enc_ty = enc_ty
        self.sort_order = sort_order

    def to_vl_obj(self):
        res = {"field": self.field, "type": self.enc_ty}
        if self.channel in ["y2", "x2"]:
            # in vegalite, y2 should not have type since it should be consistent to y
            res.pop("type")
        if self.sort_order:
            res["sort_order"] = self.sort_order
        return res