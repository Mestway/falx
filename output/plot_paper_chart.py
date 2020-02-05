import argparse
import json
import os
import pandas as pd
from pprint import pprint
import numpy as np
from vega import VegaLite
#from ipywidgets import widgets, interact, interactive, fixed, interact_manual
#from IPython.display import clear_output

import matplotlib
import matplotlib.pyplot as plt

# default directories
OUTPUT_DIR = os.path.join(".")
MAX_TIME = 600

def parse_log_content(exp_id, data_id, lines):
    """parse a log file"""
    status = {
        "exp_id": exp_id,
        "data_id": data_id,
        "num_candidates": [],
        "time": MAX_TIME
    }
    for i, l in enumerate(lines):
        if l.startswith("# candidates before getting the correct solution: "):
            status["num_candidates"].append(int(l.split(":")[-1].strip()) + 1)
        if l.startswith("# time used (s): "):
            status["time"] = float(l.split(":")[-1].strip())
            status["time"] = MAX_TIME if status["time"] > MAX_TIME else status["time"]
    status["solved"] = False if status["time"] >= MAX_TIME else True
    status["num_explored"] = sum(status["num_candidates"])
    status.pop("num_candidates")
    return status

def read_log_result_list(log_dir_list, titles=None):
    all_result = {}
    for i, log_dir in enumerate(log_dir_list):
        log_result = []
        for fname in os.listdir(log_dir):
            if not fname.endswith(".log"): continue
            fpath = os.path.join(log_dir, fname)
            title = log_dir if titles is None else titles[i]
            with open(fpath) as f:
                status = parse_log_content(title, fname.split(".")[0], f.readlines())
                log_result.append(status)
        all_result[title] = log_result
    return all_result

def calculate_cdf(log_data, X):
    Y = []
    for x in X:
        cnt = len([l for l in log_data if l["time"] < x])
        Y.append(cnt)
    return Y
        
X = np.linspace(0, 600, 2000)
res = read_log_result_list(["exp_falx_4", "exp_none_4_all", "exp_morpheus_4"], ["Viser", "Enum", "Morpheus"])
Y1 = calculate_cdf(res["Viser"], X)
Y2 = calculate_cdf(res["Enum"], X)
Y3 = calculate_cdf(res["Morpheus"], X)
fig, ax = plt.subplots(figsize=(5,4))

mp = {}
for r in res["Viser"]:
    mp[r["data_id"]] = {
        "viser": r["time"]
    }
for r in res["Morpheus"]:
    mp[r["data_id"]]["morpheus"] = r["time"]

sumval = 0
cnt = 0
for data_id in mp:
    if mp[data_id]["viser"] != 600 and mp[data_id]["morpheus"] != 600 and mp[data_id]["morpheus"] > 5:
        sumval += mp[data_id]["morpheus"] / mp[data_id]["viser"]
        cnt += 1
print(sumval / cnt)


#matplotlib.rcParams.update({'font.size': 16})

def plot_cdf_1(X, Y1, title=[]):

    ax.plot(X, Y1, label=title[0], color="g", linewidth=1)
    #ax.plot(X, Y2, label='No Decomposition')
    plt.axhline(y=35, color='grey', linestyle='--', linewidth=0.5)
    plt.axhline(y=70, color='grey', linestyle='--', linewidth=0.5)
    #ax.plot(X, Y2, label=title[1], color="b",linestyle='--', linewidth=1)
    plt.xlabel('Time (s)')
    plt.ylabel('# of solved benchmarks')

    yticks, ylabels = plt.yticks()
    yticks = list(np.arange(0, 84, 10)) + [83]
    print(yticks)
    ylabels = [x if x in [10, 20, 30, 40, 50, 60, 70, 83] else "" for x in yticks]
    plt.yticks(yticks, ylabels)

    ticks, labels = plt.xticks()
    ticks = np.arange(0, 610, 10)
    labels = [x if x in [10, 60, 120, 300, 600] else "" for x in ticks]
    #plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 83])
    plt.xticks(ticks, labels)
    plt.legend()
    plt.show()

def plot_cdf(X, Y1, Y2, title=[]):
    for i in range(len(X)):
        print(X[i], Y2[i])
    ax.plot(X, Y1, label=title[0], color="g", linewidth=1)
    #ax.plot(X, Y2, label='No Decomposition')
    plt.axhline(y=35, color='grey', linestyle='--', linewidth=0.5)
    plt.axhline(y=70, color='grey', linestyle='--', linewidth=0.5)
    ax.plot(X, Y2, label=title[1], color="b",linestyle='--', linewidth=1)
    plt.xlabel('Time (s)')
    plt.ylabel('# of solved benchmarks')

    yticks, ylabels = plt.yticks()
    yticks = list(np.arange(0, 84, 10)) + [83]
    print(yticks)
    ylabels = [x if x in [10, 20, 30, 40, 50, 60, 70, 83] else "" for x in yticks]
    plt.yticks(yticks, ylabels)

    ticks, labels = plt.xticks()
    ticks = np.arange(0, 610, 10)
    labels = [x if x in [10, 60, 120, 300, 600] else "" for x in ticks]
    #plt.yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 83])
    plt.xticks(ticks, labels)
    plt.legend()
    plt.show()

#plot_cdf_1(X, Y1, title=["Viser"])
#plot_cdf(X, Y1, Y2, title=["Viser", "No Decomposition"])
#plot_cdf(X, Y1, Y3, title=["Viser", "Viser-M"])
