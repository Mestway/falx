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
        "max_prog_size": 4,

        "grammar": {
            "operators": [  "gather_neg", "unite","mutate_custom","filter", "separate", "spread",  "cumsum", 
                "gather", "mutate", "group_sum"],
            "filer_op": [">", "<", "=="],
            "constants": [],
            "aggr_func": ["sum", "count"], #"mean", 
            "mutate_op": ["+", "-"],
            "gather_max_val_list_size": 3,
            "gather_max_key_list_size": 3,
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
            
            if fname not in ["048.json"]:
                continue

            # large table
            #if fname in ["033.json", "033-2.json"]:
            #   continue

            # too complex
            #if fname in ["048.json"]:
            #    continue
            
            # unsupported
            if fname in ["test_3.json", "028.json", "060.json", "057.json", "036.json", "019.json"]:
                continue

            #if fname in ['050.json', 'test_21.json', '007.json', '011.json', '046.json', '031.json', 'test_17.json', '027.json', '026.json', 'test_16.json', '030.json', 'test_1.json', '047.json', '002-2.json', '010.json', '006.json', 'test_20.json', '051.json', '037.json', 'test_11.json', '021.json', '056.json', '001.json', '017.json', '040.json', '039-1.json', 'test_6.json', 'test_7.json', '041.json', '016.json', '020.json', 'test_10.json', '023.json', 'test_13.json', 'test_8.json', '035.json', '058.json', '039.json', 'test_4.json', '042.json', '015.json', '003.json', '054.json', '055.json', '003-2.json', '002.json', '014.json', '043.json', 'test_5.json', '038.json', '059.json', '018.json', '034.json', 'test_12.json', 'test_9.json', '022.json', '029.json', 'test_19.json', 'test_2.json', '044.json', '002-1.json', '013.json', '005.json', 'test_23.json', '052.json', '025.json', 'test_15.json', '033.json']:
            #    continue
            
            fpath = os.path.join(DATA_DIR, fname)
            current_config = copy.deepcopy(config)
            run_wrapper(fpath, 4, current_config, capturing=True)
