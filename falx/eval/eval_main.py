import warnings
warnings.filterwarnings('ignore')

from io import StringIO 
import sys

import logging

import copy

import json
import pandas as pd
import os
from vega import VegaLite
#from ipywidgets import widgets
import numpy as np

import time

from falx.visualization.chart import *
from falx.eval.eval_interface import *
import timeout_decorator


level    = logging.INFO
format   = '  %(message)s'
handlers = [logging.FileHandler(f'eval_log_{time.time()}.log'), logging.StreamHandler()]

logging.basicConfig(level = level, format = format, handlers = handlers)

DATA_DIR = os.path.join("..", "..", "benchmarks")

np.random.seed(2019)

class Capturing(list):
    def __enter__(self):
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = self._stringio = StringIO()
        sys.stderr = self._stringio
        return self
    def __exit__(self, *args):
        self.extend(self._stringio.getvalue().splitlines())
        del self._stringio    # free up some memory
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        
def render_vegalite(vis):
    # Render a visualization using vegalite
    VegaLite(vis.to_vl_obj()).display()
            
            
def run_wrapper(fpath, num_samples, config, capturing=True):
    logging.info("\n====> {}".format(fpath))
    start_time = time.time()
    
    no_error = True
    
    current_config = copy.deepcopy(config)
    
    for allow_comp_without_new_val in [False, True]:

        current_config["grammar"]["allow_comp_without_new_val"] = allow_comp_without_new_val
        if capturing:
            with Capturing() as output:
                try:
                    candidates = run_synthesis(fpath, num_samples, current_config)
                except:
                    candidates = {}
                    no_error = False
        else:
            candidates = run_synthesis(fpath, num_samples, current_config)

       # give a second try
        if len(candidates.items()) == 0:
            logging.info("[retry]")

    if no_error:
        logging.info(f"[Solution] {len(candidates)} solutions found.")
    else:
         logging.info(f"[Solution] ERROR.")
            
    logging.info(f"[time] {time.time() - start_time}")
    for key, prog_pair in candidates.items():
        p, vis = prog_pair[0]
        logging.info("# table_prog:")
        logging.info("  {}".format(p))
        logging.info("# vis_spec:")
        vl_obj = vis.to_vl_obj()
        data = vl_obj.pop("data")["values"]
        logging.info("    {}".format(vl_obj))
        logging.info("\n")

if __name__ == '__main__':
    config = {
        # configurations related to table transformation program synthesizer
        "solution_sketch_limit": 1,
        "solution_limit": 1,
        "time_limit_sec": 600,
        "max_prog_size": 3,

        "grammar": {
            "operators": [  "gather_neg", "unite","mutate_custom","filter", "separate", "spread",  "cumsum", 
                "gather", "mutate", "group_sum"],
            "filer_op": [">", "<", "=="],
            "constants": [],
            "aggr_func": ["sum", "count"], #"mean", 
            "mutate_op": ["+", "-"],
            "gather_max_val_list_size": 6,
            "gather_max_key_list_size": 6,
            "consider_non_consecutive_gather_keys": False,
            "allow_comp_without_new_val": False
        },

        "disable_provenance_analysis": True, # there is a issue with provenance analysis with mutate

        # set the visualization backend, one of "vegalite, ggplot2, matplotlib"
        # ggplot2 and matplotlib have some feature restrictions
        "vis_backend": "vegalite"
    }

    for fname in os.listdir(DATA_DIR):
        if fname.endswith("json") and "discard" not in fname:
            
            # if fname not in ["test_16.json"]:
            #     continue

            # large table
            # if fname in ["033.json", "033-2.json"]:
            #    continue

            # too complex
            if fname in ["048.json"]:
                continue
            
            # unsupported
            if fname in ["test_3.json", "028.json", "060.json", "057.json", "036.json", "019.json"]:
                continue
            
            fpath = os.path.join(DATA_DIR, fname)
            current_config = copy.deepcopy(config)
            run_wrapper(fpath, 4, current_config, capturing=True)
