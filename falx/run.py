import argparse
import json
import pandas as pd
import os
from pprint import pprint

from chart import VisDesign
import design_validator
import design_enumerator
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

def test_benchmarks(data_dir, data_id):
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

        input_data = table_utils.load_and_clean_table(data["input_data"])
        vis = VisDesign.load_from_vegalite(data["vl_spec"], data["output_data"])
        trace = vis.eval()

        result = Falx.synthesize(inputs=[input_data], vtrace=trace)

        print("## synthesize result for task {}".format(fname))
        for p, vis in result:
            print("table_prog:")
            print(p)
            print("vis_spec:")
            print(vis.to_vl_json(indent=2))

if __name__ == '__main__':
    flags = parser.parse_args()
    test_benchmarks(flags.data_dir, flags.data_id)
