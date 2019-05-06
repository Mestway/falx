import argparse
import json
import pandas as pd
import os
from pprint import pprint

from chart import VisDesign
import design_validator
import design_enumerator
from interface import FalxTask
import table_utils

import morpheus

# default directories
PROJ_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DATA_DIR = os.path.join(PROJ_DIR, "benchmarks")

# arguments
parser = argparse.ArgumentParser()
parser.add_argument("--data_dir", dest="data_dir", default=DATA_DIR, help="the directory of all benchmarks")

def test_benchmarks(data_dir):
    """load the dataset into panda dataframes """
    benchmarks = []
    for fname in os.listdir(data_dir):
        #if "031.json" not in fname: continue
        if fname.endswith(".json"):
            with open(os.path.join(data_dir, fname), "r") as f:
                data = json.load(f)

            if not "vl_spec" in data: 
                # ignore cases that do not have vl specs
                continue

            print("======= {}".format(fname))

            input_data = table_utils.load_and_clean_table(data["input_data"])
            vis = VisDesign.load_from_vegalite(data["vl_spec"], data["output_data"])
            trace = vis.eval()

            task = FalxTask(inputs=[input_data], vtrace=trace)
            task.synthesize()


if __name__ == '__main__':
    flags = parser.parse_args()
    test_benchmarks(flags.data_dir)
