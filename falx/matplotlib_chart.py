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

    def render(self):
        self.chart.render(self.df)
        plt.legend()


class MultiLayer(object):
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


class Subplot(object):
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
    

class BarChart(object):
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


class GroupBarChart(object):
    def __init__(self, c_x, c_ys, stacked=False, orient="vertical"):
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


class ScatterPlot(object):
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


class LineChart(object):
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


class AreaChart(object):
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
