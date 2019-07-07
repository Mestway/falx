import json
import copy
from pprint import pprint

import itertools

import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

from symbolic import SymTable, SymVal
import table_utils

import visual_trace
from visual_trace import BarV, BarH, Point, Line, Area, Box
from chart import VisDesign, remove_unused_fields

def build_color_map(values):
    distinct_vals = list(set(values))
    cmap = matplotlib.cm.viridis
    colors = cmap(np.linspace(0, 1, len(distinct_vals)))
    return {v:colors[distinct_vals.index(v)] for v in distinct_vals}


class MatplotlibChart(object):
    """Top level visualization construct """
    def __init__(self, df, chart):
        # data should be a dataframe
        # is a table with 3 columns "a", "b", "c" and two rows
        self.df = df
        self.chart = chart

    def eval(self):
        return self.chart.eval(self.df)

    @staticmethod
    def inv_eval(vtrace):
        res = []
        for data, chart in MpMultiLayer.inv_eval(vtrace):
            if isinstance(data, (list,)):
                for d in data:
                    d.values.sort(key=lambda x: json.dumps(x))
            else:
                data.values.sort(key=lambda x: json.dumps(x))
            res.append((data, chart))
        return res

    def render(self):
        self.chart.render(self.df)
        plt.legend()


class MpMultiLayer(object):
    def __init__(self, charts):
        self.charts = charts

    def eval(self, df):
        trace = []
        for chart in self.charts:
            trace += chart.eval(df)
        return trace

    def render(self, df, ax=None):
        ax = plt if ax is None else ax
        for chart in self.charts:
            chart.render(df, ax)

    @staticmethod
    def inv_eval(vtrace):
        """returns a list of (abs_table, layer) pairs. """
        trace_layer = visual_trace.partition_trace(vtrace)
        
        layers = {}
        for vty in trace_layer:
            layers[vty] = MpSubplot.inv_eval(trace_layer[vty], vty)

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
                data_for_all_layers = [cl[0] for cl in data_layer_pairs]
                all_layers = [cl[1] for cl in data_layer_pairs]
                res.append((data_for_all_layers, MpMultiLayer(charts=all_layers)))
            return  res


class MpSubplot(object):
    def __init__(self, chart, column):
        self.chart = chart
        self.column = column

    def eval(self, df):
        full_trace = []
        group = df[self.column]
        for g in np.unique(group):
            i = np.where(group == g)
            sub_df = df.loc[i]
            trace = self.chart.eval(sub_df)
            for e in trace:
                e.column = g
            full_trace += trace
        return full_trace

    def render(self, df):
        """render the visualization """
        group = df[self.column]
        num_group = len(np.unique(group))

        fig, axes = plt.subplots(1,num_group,figsize=(num_group * 5,5),sharex=True,sharey=True)
        for ax, g in zip(axes, np.unique(group)):
            i = np.where(group == g)
            sub_df = df.loc[i]
            self.chart.render(sub_df, ax)
            ax.set_xlabel(g)

    @staticmethod
    def inv_eval(vtrace, vty):

        def synth_per_case(_vtrace, _vty):
            if _vty == "BarV":
                l2 = MpGroupBarChart.inv_eval(_vtrace, orientation="vertical")
                l1 = MpBarChart.inv_eval(_vtrace, orientation="vertical")
                return l1 + l2
            elif _vty == "BarH":
                l2 = MpGroupBarChart.inv_eval(_vtrace, orientation="horizontal")
                l1 = MpBarChart.inv_eval(_vtrace, orientation="horizontal")
                return l1 + l2
            elif _vty == "Point":
                return MpScatterPlot.inv_eval(_vtrace)
            elif _vty == "Line":
                return MpLineChart.inv_eval(_vtrace)
            elif _vty == "Area":
                return MpAreaChart.inv_eval(_vtrace)

        use_column = any([vt.column is not None for vt in vtrace])
        if not use_column:
            return synth_per_case(vtrace, vty)

        partition = {}
        for vt in vtrace:
            if vt.column not in partition:
                partition[vt.column] = []
            partition[vt.column].append(vt)

        res = []
        chart = None
        table = []
        for col in partition:
            layer_cand = synth_per_case(partition[col], vty)
            if layer_cand == []:
                return []
            col_table = layer_cand[0][0].values
            if chart == None:
                chart = layer_cand[0][1]
            for r in col_table:
                r["c_column"] = col
            table = table + col_table
        return [(SymTable(values=table), MpSubplot(chart, "c_column"))]

    

class MpBarChart(object):
    def __init__(self, c_x, c_height, c_bot=None, 
                 c_color=None, orient="vertical"):
        self.c_x = c_x
        self.c_height = c_height
        self.c_bot = c_bot
        self.c_color = c_color
        self.orient = orient

    def eval(self, df):
        """generate row by row """
        data = df.to_dict(orient="records")
        trace = []
        for t in data:
            x = t[self.c_x]
            y1 = t[self.c_bot] if self.c_bot is not None else 0
            y2 = y1 + t[self.c_height]
            c = t[self.c_color] if self.c_color is not None else None
            if self.orient == "vertical":
                tr = BarV(x=x,y1=y1,y2=y2,color=c)
            elif self.orient == "horizontal":
                tr = BarH(y=x,x1=y1,x2=y2,color=c)
            trace.append(tr)
        return trace

    def render(self, df, ax=None):
        """group by color """
        ax = plt if ax is None else ax

        if self.c_color:
            # partition by each color and then plot
            group = df[self.c_color]
            color_map = build_color_map(group) 
            partitions = [(g, df.loc[np.where(group == g)]) for g in np.unique(group)]
            for g, sub_df in partitions:
                if self.orient == "vertical":
                    ax.bar(x=sub_df[self.c_x], height=sub_df[self.c_height], 
                           bottom=sub_df[self.c_bot], color=color_map[g], label=g)
                else:
                    ax.barh(y=sub_df[self.c_x], width=sub_df[self.c_height], 
                            left=sub_df[self.c_bot], color=color_map[g], label=g)
        else:
            if self.orient == "vertical":
                ax.bar(x=df[self.c_x], height=df[self.c_height], bottom=df[self.c_bot], label=self.c_height)
            else:
                ax.barh(y=df[self.c_x], width=df[self.c_height], left=df[self.c_bot], label=self.c_height)        

    @staticmethod
    def inv_eval(vtrace, orientation):
        data_values = []
        if orientation == "vertical":
            for vt in vtrace:
                bot = None if vt.y2 is None else vt.y1
                height = vt.y1 if vt.y2 is None else vt.y2 - vt.y1
                data_values.append({"c_x": vt.x, "c_bot": bot, "c_height": height, "c_color": vt.color})
        if orientation == "horizontal":
            for vt in vtrace:
                bot = None if vt.x2 is None else vt.x1
                height = vt.x1 if vt.x2 is None else vt.x2 - vt.x1
                data_values.append({"c_x": vt.y, "c_bot": bot, "c_height": height, "c_color": vt.color})
               
        # remove fields that contain none values
        unused_fields = remove_unused_fields(data_values)

        bar_chart = MpBarChart(c_x="c_x", c_bot="c_bot" if "c_bot" not in unused_fields else None, 
                               c_height="c_height", c_color="c_color" if "c_color" not in unused_fields else None,
                               orient=orientation)
        return [(SymTable(values=data_values), bar_chart)]


class MpGroupBarChart(object):
    def __init__(self, c_x, c_ys, stacked=True, orient="vertical"):
        self.c_x = c_x
        self.c_ys = c_ys
        self.stacked=stacked
        self.orient=orient

    def eval(self, df):
        data = df.to_dict(orient="records")
        trace = []
        for t in data:
            last_y = 0
            for c_y in self.c_ys:
                x = t[self.c_x]
                h = t[c_y]
                y1 = 0 if not self.stacked else last_y
                y2 = h if not self.stacked else last_y + h
                last_y += h
                if self.orient == "vertical":
                    tr = BarV(x=x,y1=y1,y2=y2,color=c_y)
                elif self.orient == "horizontal":
                    tr = BarH(y=x,x1=y1,x2=y2,color=c_y)
                trace.append(tr)
        return trace

    def render(self, df, ax=None):
        if ax == plt: ax = None
        kind = "barh" if self.orient == "horizontal" else "bar"
        df.plot(kind=kind, x=self.c_x, y=self.c_ys, stacked=self.stacked, ax=ax)

    @staticmethod
    def inv_eval(vtrace, orientation):
        # map x to multiple y
        print(vtrace)
        table_dict = {}
        y_cols = list(set([vt.color for vt in vtrace]))
        for vt in vtrace:
            if orientation == "vertical":
                if vt.x not in table_dict:
                    table_dict[vt.x] = {"c_x": vt.x}
                if vt.y2 is None or vt.color is None:
                    return []
                table_dict[vt.x][vt.color] = vt.y2 - vt.y1
            else:
                if vt.y not in table_dict:
                    table_dict[vt.y] = {"c_x": vt.y}
                if vt.x2 is None or vt.color is None:
                    return []
                table_dict[vt.y][vt.color] = vt.x2 - vt.x1
        table_content = []
        for x in table_dict:
            table_content.append(table_dict[x])
            if len(table_dict[x]) != len(y_cols) + 1:
                # cannot  represented in mp format
                return []

        return [(SymTable(values=table_content), MpGroupBarChart("c_x", y_cols, orient=orientation))]


class MpScatterPlot(object):
    def __init__(self, c_x, c_ys, c_size=None):
        assert(isinstance(c_ys, (list,tuple,)))
        self.c_x = c_x
        self.c_ys = c_ys
        self.c_size = c_size

    def eval(self, df):
        data = df.to_dict(orient="records")
        trace = []
        for t in data:
            for c_y in self.c_ys:
                x = t[self.c_x]
                y = t[c_y]
                size = t[self.c_size] if self.c_size is not None else None
                tr = Point(shape="point", x=x,y=y,size=size,color=c_y)
                trace.append(tr)
        return trace

    def render(self, df, ax=None):
        """group by color """
        ax = plt if ax is None else ax
        color_map = build_color_map(self.c_ys)
        for c_y in self.c_ys:
            size = df[self.c_size] if self.c_size is not None else None
            ax.scatter(x=df[self.c_x], y=df[c_y], s=size, color=color_map[c_y], label=c_y)

    @staticmethod
    def inv_eval(vtrace):
        table_dict = {}
        y_cols = list(set([vt.color for vt in vtrace]))

        size_used = any([vt.size != None for vt in vtrace])

        if any([vt.shape != None for vt in vtrace]) or (len(y_cols) > 1 and size_used):
            # does not support shape or size + color
            return []

        if len(y_cols) > 1:
            # map x to multiple y
            table_dict = {}
            for vt in vtrace:
                if vt.x not in table_dict:
                    table_dict[vt.x] = {"c_x": vt.x}
                table_dict[vt.x][str(vt.color)] = vt.y

            table_content = []
            for x in table_dict:
                table_content.append(table_dict[x])
                if len(table_dict[x]) != len(y_cols) + 1:
                    # we require table to contain NA values
                    return []
            chart = MpScatterPlot("c_x", [str(y) for y in y_cols])
            return [(SymTable(values=table_content), chart)]
        else:
            table_content = []
            for vt in vtrace:
                r = {"c_x": vt.x, "c_y": vt.y}
                if size_used:
                    r["c_size"] = vt.size
                    c_size = "c_size"
                else:
                    c_size = None

                table_content.append(r)
                chart = MpScatterPlot("c_x", ["c_y"], c_size)
            return [(SymTable(values=table_content), chart)]

class MpLineChart(object):
    def __init__(self, c_x, c_ys):
        assert(isinstance(c_ys, (list,tuple,)))
        self.c_x = c_x
        self.c_ys = c_ys

    def eval(self, df):
        data = df.to_dict(orient="records")
        # sort by x
        data = sorted(data, key=lambda t: t[self.c_x])
        trace = []
        for i in range(len(data) - 1):
            t1 = data[i]
            t2 = data[i + 1]
            for c_y in self.c_ys:
                x1, y1 = t1[self.c_x], t1[c_y]
                x2, y2 = t2[self.c_x], t2[c_y]
                tr = Line(x1=x1,y1=y1,x2=x2,y2=y2,color=c_y)
                trace.append(tr)
        return trace

    def render(self, df, ax=None):
        """group by color """
        ax = plt if ax is None else ax
        color_map = build_color_map(self.c_ys)
        for c_y in self.c_ys:
            ax.plot(df[self.c_x], df[c_y], color=color_map[c_y], label=c_y)

    @staticmethod
    def inv_eval(vtrace):
        # frozen data used for removing duplicate points
        frozen_data = []
        for vt in vtrace:
            # each end of an point will only be added once
            p1 = json.dumps({"c_x": vt.x1, "c_y": vt.y1, "c_size": vt.size, "c_color": vt.color, "c_column": vt.column}, sort_keys=True)
            p2 = json.dumps({"c_x": vt.x2, "c_y": vt.y2, "c_size": vt.size, "c_color": vt.color, "c_column": vt.column}, sort_keys=True)
            if p1 not in frozen_data: frozen_data.append(p1)
            if p2 not in frozen_data: frozen_data.append(p2)

        data_values = [json.loads(r) for r in frozen_data]

        unused_fields = remove_unused_fields(data_values)

        if "c_color" not in unused_fields and "c_size" not in unused_fields:
            assert False

        col_num = 2
        y_cols = None
        if "c_color" not in unused_fields:
            y_cols = list(set([r["c_color"] for r in data_values]))
            col_num = 1 + len(y_cols)
            # map x to multiple y
            table_dict = {}
            for r in data_values:
                if r["c_x"] not in table_dict:
                    table_dict[r["c_x"]] = {"c_x": r["c_x"]}
                table_dict[r["c_x"]][r["c_color"]] = r["c_y"]

            table_content = []
            for x in table_dict:
                table_content.append(table_dict[x])
                if len(table_dict[x]) != col_num:
                    # we require table to contain NA values
                    return []
        else:
            y_cols = ["c_y"]
            if "c_size" not in unused_fields:
                y_cols.append(["c_size"])
            table_content = data_values

        return [(SymTable(values=table_content, constraints=[]), MpLineChart("c_x", y_cols))]



class MpAreaChart(object):
    def __init__(self, c_x, c_tops, c_bots=None):
        self.c_x = c_x
        self.c_tops = c_tops
        self.c_bots = c_bots
        assert(c_bots is None or len(c_bots) == len(c_tops))

    def eval(self, df):
        data = df.to_dict(orient="records")
        data = sorted(data, key=lambda t: t[self.c_x])
        trace = []
        for i in range(len(data) - 1):
            if self.c_bots is not None:
                for c_top, c_bot in zip(self.c_tops, self.c_bots):
                    t1 = data[i]
                    t2 = data[i + 1]
                    x1, top1, bot1 = t1[self.c_x], t1[c_top], t1[c_bot]
                    x2, top2, bot2 = t2[self.c_x], t2[c_top], t2[c_bot]
                    tr = Area(x1=x1,yt1=top1,yb1=bot1,x2=x2,yt2=top2,yb2=bot2,color=c_top)
                    trace.append(tr)
            else:
                for c_top in self.c_tops:
                    t1 = data[i]
                    t2 = data[i + 1]
                    x1, top1 = t1[self.c_x], t1[c_top]
                    x2, top2 = t2[self.c_x], t2[c_top]
                    tr = Area(x1=x1,yt1=top1,yb1=0,x2=x2,yt2=top2,yb2=0,color=c_top)
                    trace.append(tr)
        return trace

    def render(self, df, ax=None):
        ax = plt if ax is None else ax
        if self.c_bots is not None:
            for c_top, c_bot in zip(self.c_tops, self.c_bots):
                ax.fill_between(df[self.c_x], df[c_top], df[c_bot], label=c_top)
        else:
            for c_top in self.c_tops:
                ax.fill_between(df[self.c_x], df[c_top], label=c_top)

    @staticmethod
    def inv_eval(vtrace):
        use_color = all([vt.color != None for vt in vtrace])
        if not use_color:
            # simple viusal trace
            all_start_from_zero = all([vt.yb1 == 0 and vt.yb2 == 0 for vt in vtrace])
            table_content = []
            for vt in vtrace:
                if all_start_from_zero:
                    table_content.append({"c_x": vt.x1, "c_top": vt.yt1})
                    table_content.append({"c_x": vt.x2, "c_top": vt.yt2})
                else:
                    table_content.append({"c_x": vt.x1, "c_top": vt.yt1, "c_bot": vt.yb1})
                    table_content.append({"c_x": vt.x2, "c_top": vt.yt2, "c_bot": vt.yb2})
            chart = MpAreaChart(c_x="c_x", c_tops=["c_top"], c_bots=None if all_start_from_zero else ["c_bot"])
            return [(SymTable(values=table_content), chart)]
        else:
            # map x to multiple y
            color_names = list(set([vt.color for vt in vtrace]))
            table_dict = {}
            for vt in vtrace:
                if vt.x1 not in table_dict:
                    table_dict[vt.x1] = {"c_x": vt.x1}
                if vt.x2 not in table_dict:
                    table_dict[vt.x2] = {"c_x": vt.x2}
                table_dict[vt.x1]["{}".format(str(vt.color))] = (vt.yt1 - vt.yb1) if vt.yb1 is not None else vt.yt1
                table_dict[vt.x2]["{}".format(str(vt.color))] = (vt.yt2 - vt.yb2) if vt.yb2 is not None else vt.yt2

            table_content = []
            for x in table_dict:
                table_content.append(table_dict[x])
                if len(table_dict[x]) != len(color_names) + 1:
                    # we require table to contain NA values
                    return []
            chart = MpScatterPlot("c_x", ["{}".format(c) for c in color_names])
            return [(SymTable(values=table_content), chart)]

import os
import json

data_dir = "../benchmarks"

if __name__ == '__main__':
    test_target = ["048.json"]#["{:03d}.json".format(i) for i in range(1, 61)] #["038.json", "002.json", "003.json", "004.json"]
    for fname in test_target:
        with open(os.path.join(data_dir, fname), "r") as f:
            data = json.load(f)
            vis = VisDesign.load_from_vegalite(data["vl_spec"], data["output_data"])
            trace = vis.eval()
            ad_list = [VisDesign.inv_eval(trace), MatplotlibChart.inv_eval(trace)]
            print("========")
            print(fname)
            for abstract_designs in ad_list:
                print('---')
                for full_sym_data, chart in abstract_designs:
                    if isinstance(full_sym_data, (list,)):
                        for sym_data in full_sym_data:
                            pprint(sym_data.values[:min([len(sym_data.values), 10])])
                    else:
                        pprint(full_sym_data.values[:min([len(full_sym_data.values), 10])])

