import json
import copy
from pprint import pprint

from namedlist import namedlist

import utils

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
        """inverse evaluation of a visual trace 
        Args: vtrace: a visual trace
        Returns: a list of pairs (data, vis) s.t. vis(data)=vtrace
        """
        res = []
        for data, chart in GroupChart.inv_eval(vtrace):
            res.append(VisDesign(data, chart).to_vl_json())
        return res


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

    @staticmethod
    def inv_eval(vtrace):
        # partition trace elements into groups
        trace_group = {}
        for v in vtrace:
            if v.group not in trace_group:
                trace_group[v.group] = []
            trace_group[v.group].append(v)

        chart_str_to_chart = {}
        group_data_chart = {}
        for g in trace_group:
            # each group is a dictionary in the form of: {chart_str: (data, chart)}
            data_chart_pairs = LayeredChart.inv_eval(trace_group[g])
            for dc in data_chart_pairs:
                chart_str_to_chart[dc[1].to_vl_json()] = dc[1]
            group_data_chart[g] = {dc[1].to_vl_json():dc[0] for dc in data_chart_pairs}
        
        # get all specs for all groups and find shared specs
        group_chart_specs = {g:list(group_data_chart[g].keys()) for g in group_data_chart}
        common_charts = set.intersection(*map(set,[group_chart_specs[g] for g in group_chart_specs]))

        res = []
        for chart_str in common_charts:
            chart = chart_str_to_chart[chart_str]
            group_data = {g:group_data_chart[g][chart_str] for g in group_data_chart}
            for g in group_data:
                for r in group_data[g]:
                    r["c_group"] = g 
            data = [d for g in group_data for d in group_data[g]]
            
            chart = GroupChart(layer=chart, enc_group=Encoding(channel="column", field="c_group", enc_ty="nominal"))
            res.append((data, chart))
        return res


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

    def to_vl_json(self):
        return json.dumps(self.to_vl_obj())

    def eval(self, data):
        """obtain elements in each layer and put them together. """
        result = []
        for layer in self.layers:
            inst_layer = copy.copy(layer)
            for e in self.shared_encodings:
                inst_layer.encodings[e] = self.shared_encodings[e]
            result += inst_layer.eval(data)
        return result

    @staticmethod
    def inv_eval(vtrace):
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

        if len(layers) == 1:
            # directly return the layer if there is only one layer
            return layers[list(layers.keys())[0]]
        else:
            pass #return (LayeredChart(layers=layers,shared_encodings=[],resolve={}))


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

    def to_vl_json(self):
        return json.dumps(self.to_vl_obj())

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
        data = []
        if orientation == "vertical":
            for vt in vtrace:
                data.append({"c_x": vt.x, "c_y": vt.y1, "c_y2": vt.y2})
            
            encodings = []
            for channel, enc_ty in [("x", "nominal"), ("y", "quantitative"), ("y2", "quantitative")]:
                field_name = "c_{}".format(channel)
                encodings.append(Encoding(channel, field_name, enc_ty))

            bar_chart = BarChart(encodings=encodings, orientation=orientation)

        elif orientation == "horizontal":
            for vt in vtrace:
                data.append({"c_x": vt.x1, "c_x2": vt.x2, "c_y": vt.y})

            encodings = []
            for channel, enc_ty in [("x", "quantitative"), ("x2", "quantitative"), ("y", "nominal")]:
                field_name = "c_{}".format(channel)
                encodings.append(Encoding(channel, field_name, enc_ty))
            bar_chart = BarChart(encodings=encodings, orientation=orientation)
        else:
            print('[Error] orientation should be vertical or horizontal, given: {}'.format(orientation))
        return [(data, bar_chart)]


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
        """inverse construction of vertical bars """
        if ((orientation=="horizontal" and any([vt.x1 is None or vt.x2 is None for vt in vtrace]))
            or (orientation=="vertical" and any([vt.y1 is None or vt.y2 is None for vt in vtrace]))):
                # it does not satisfy stacked bar semantics
                return []
        data = []
        if orientation == "vertical":
            # vertical stacked bar
            for vt in vtrace:
                data.append({"c_x": vt.x, "c_y": vt.y2 - vt.y1, "c_color": vt.color})
            encodings = []
            for channel, enc_ty in [("x", "nominal"), ("y", "quantitative"), ("color", "nominal")]:
                field_name = "c_{}".format(channel)
                encodings.append(Encoding(channel, field_name, enc_ty))
        elif orientation == "horizontal":
            # horizontal stacked bar
            for vt in vtrace:
                data.append({"c_x": vt.x2 - vt.x1, "c_y": vt.y, "c_color": vt.color})
            encodings = []
            for channel, enc_ty in [("x", "quantitative"), ("y", "nominal"), ("color", "nominal")]:
                field_name = "c_{}".format(channel)
                encodings.append(Encoding(channel, field_name, enc_ty))

        bar_chart = StackedChart(chart_ty="bar", encodings=encodings, orientation=orientation)
        return [(data, bar_chart)]

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

    def to_vl_json(self):
        return json.dumps(self.to_vl_obj())

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
        frozen_data = []
        for vt in vtrace:
            # each end of an point will only be added once
            p1 = json.dumps({"c_x": vt.x1, "c_y": vt.y1, "c_size": vt.size, "c_color": vt.color}, sort_keys=True)
            p2 = json.dumps({"c_x": vt.x2, "c_y": vt.y2, "c_size": vt.size, "c_color": vt.color}, sort_keys=True)
            if p1 not in frozen_data: frozen_data.append(p1)
            if p2 not in frozen_data: frozen_data.append(p2)
        
        data = [json.loads(r) for r in frozen_data]

        encodings = []
        for channel, enc_ty in [("x", "_"), ("y", "_"), ("size", "nominal"), ("color", "nominal")]:
            field_name = "c_{}".format(channel)
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
            res.append(Point(x=x, y=y, color=color, size=size, shape=shape))
        return res

    @staticmethod
    def inv_eval(vtrace):
        data = []
        for vt in vtrace:
            data.append({"c_x": vt.x, "c_y": vt.y, "c_size": vt.size, "c_color": vt.color, "c_shape": vt.shape})

        # remove fields that contain none values
        unused_fields = []# [key for key in data[0] if any([r[key] is None for r in data])]
        for r in data:
            for k in unused_fields:
                r.pop(k)

        encodings = []
        for channel, enc_ty in [("x", "_"), ("y", "_"), 
                                ("size", "_"), ("color", "nominal"), ("shape", "nominal")]:
            field_name = "c_{}".format(channel)
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
        if self.sort_order:
            res["sort_order"] = self.sort_order
        return res