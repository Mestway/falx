import argparse
import json
import pandas as pd
import os
from pprint import pprint

from chart import VisDesign
from eval_interface import FalxEvalInterface
from interface import Falx
import table_utils

import morpheus

# default directories
PROJ_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DATA_DIR = os.path.join(PROJ_DIR, "benchmarks")

# arguments
parser = argparse.ArgumentParser()
parser.add_argument("--data_dir", dest="data_dir", default=DATA_DIR, help="the directory of all benchmarks")
parser.add_argument("--data_id", dest="data_id", default="001", 
                    help="the id of the benchmark, if None, it runs for all tests in the data_dir")
parser.add_argument("--mode", dest="mode", default="eval", 
                    help="Enter the running mode: [eval] or [run]")

def test_benchmarks(data_dir, data_id, mode):
    """load the dataset into panda dataframes """
    test_targets = None
    if data_id is not None:
        test_targets = [str(data_id) + '.json']
    else:
        test_targets = [fname for fname in os.listdir(data_dir) if fname.endswith(".json")]

    benchmarks = []
    for fname in test_targets:

        with open(os.path.join(data_dir, fname), "r") as f:
            data = json.load(f)

        if not "vl_spec" in data: 
            # ignore cases that do not have vl specs
            continue

        print("# run synthesize {}".format(fname))

        # read the dataset and create visualization
        input_data = data["input_data"]
        extra_consts = data["constants"] if "constants" in data else []
        vis = VisDesign.load_from_vegalite(data["vl_spec"], data["output_data"])
        trace = vis.eval()
        #pprint(trace)

        if mode == "eval":
            result = FalxEvalInterface.synthesize(inputs=[input_data], full_trace=trace, num_samples=4, extra_consts=extra_consts)
            print("## synthesize result for task {}".format(fname))
            for p, vis in result:
                print("table_prog:")
                print(p)
                print("vis_spec:")
                print(vis.to_vl_json(indent=2))
        else:
            result = Falx.synthesize(inputs=[input_data], vtrace=trace)
            print("## synthesize result for task {}".format(fname))
            for p, vis in result:
                print("table_prog:")
                print(p)
                print("vis_spec:")
                print(vis.to_vl_json(indent=2))
            #ggplot_script = vis.to_ggplot2()
            #print("\n".join(ggplot_script))

if __name__ == '__main__':
    flags = parser.parse_args()
    test_benchmarks(flags.data_dir, flags.data_id, flags.mode)
