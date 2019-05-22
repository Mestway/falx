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

        fig, axes = plt.subplots(1,num_group,figsize=(num_group * 5,5), sharex=True, sharey=True)
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
                    ax.bar(x=sub_df[self.c_x], height=sub_df[self.c_height], bottom=sub_df[self.c_bot], color=color_map[g], label=g)
                else:
                    ax.barh(y=sub_df[self.c_x], width=sub_df[self.c_height], left=sub_df[self.c_bot], color=color_map[g], label=g)
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
            last_y = 0
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
