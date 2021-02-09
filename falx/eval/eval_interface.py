import json
import itertools
from pprint import pprint
import numpy as np
import copy
import os

from falx.table import synthesizer as table_synthesizer

from falx.utils import synth_utils
from falx.utils import eval_utils
from falx.utils import vis_utils

from falx.visualization.chart import VisDesign
from falx.visualization.matplotlib_chart import MatplotlibChart
from falx.visualization import visual_trace

from falx.logger import get_logger

from pprint import pprint

np.random.seed(2019)

logger = get_logger("interface")
logger.setLevel('INFO')

class FalxEvalInterface(object):


    def group_results(results):
        """Given a list of candidate program, evaluate them and group them into equivalence classes."""
        equiv_classes = {}
        for tbl_prog, vis_spec in results:
            full_trace = vis_spec.eval()
            fronzen_trace = json.dumps(visual_trace.trace_to_table(full_trace), sort_keys=True)
            if fronzen_trace not in equiv_classes:
                equiv_classes[fronzen_trace] = []
            equiv_classes[fronzen_trace].append((tbl_prog, vis_spec))
        return equiv_classes

    @staticmethod
    def synthesize(inputs, full_trace, num_samples, extra_consts=[], group_results=False, config={}):
        """synthesize table prog and vis prog from input and output traces
        Inputs:
            input tables: a list of input tables that the synthesizer will take into consideration
            raw_trace: visualization elements in the following format
                vtrace = [
                  {"type": "line", "props": {"x1": "Y1", "y1": 0.52, "x2": "Y2", "y2": 0.57, "color": "", "column": ""}},
                  {"type": "line", "props": {"x1": "Y2", "y1": 0.57, "x2": "Y3", "y2": 0.6, "color": "", "column": ""}}
                ]
            extra_consts: extra constant that the synthesizer will take into consideration
            group_results: whether the output is grouped based on equivalence classes 
                            (i.e., the programs generate same visualizations)
            config: configurations sent to the synthesizer contains the following options
                    { "solution_sketch_limit": ..., "solution_limit":..., "time_limit_sec": ...,
                      "starting_search_program_length": 1, "stop_search_program_length": 2,
                      "grammar_base_file": "dsl/tidyverse.tyrell.base",
                      "block_sketches": [], "block_program_symbols": [], "vis_backend": "vegalite" }
        """

        # update synthesizer config
        example_trace = full_trace

        # apply inverse semantics to obtain symbolic output table and vis programs
        abstract_designs = VisDesign.inv_eval(example_trace)  
      
        # sort pairs based on complexity of tables
        abstract_designs.sort(key=lambda x: len(x[0].values[0]) 
                                if not isinstance(x[0], (list,)) else sum([len(y.values[0]) for y in x[0]]))

        candidates = []
        for full_sym_data, chart in abstract_designs:

            # split case based on single layered chart or multi layered chart
            if not isinstance(full_sym_data, (list,)):
                # single-layer chart

                synthesizer = table_synthesizer.Synthesizer(config=config["grammar"])

                if num_samples:
                    sym_data = eval_utils.sample_symbolic_table(full_sym_data, num_samples)
                else:
                    sym_data = full_sym_data

                print("==> table synthesis input:")
                #print(sym_data.instantiate())

                candidate_progs = synthesizer.enumerative_synthesis(
                                    inputs, sym_data.instantiate(), 
                                    max_prog_size=config["max_prog_size"],
                                    time_limit_sec=config["time_limit_sec"],
                                    solution_sketch_limit=config["solution_sketch_limit"],
                                    solution_limit=config["solution_limit"],
                                    disable_provenance_analysis=config["disable_provenance_analysis"])

                for p in candidate_progs:

                    output = p.eval(inputs).to_dict(orient="records")

                    field_mappings = synth_utils.align_table_schema(sym_data.values, output, find_all_alignments=True)
                    assert(len(field_mappings) > 0)

                    for field_mapping in field_mappings:
                        vis_design = VisDesign(data=output, chart=copy.deepcopy(chart))
                        vis_design.update_field_names(field_mapping)
                        candidates.append((p.stmt_string(), vis_design))


            else:
                synthesizer = table_synthesizer.Synthesizer(config=config["grammar"])
                
                sym_data = []
                for d in full_sym_data:
                    if num_samples:
                        sym_data.append(eval_utils.sample_symbolic_table(d, num_samples))
                    else:
                        sym_data.append(d)

                # multi-layer charts
                # layer_candidate_progs[i] contains all programs that transform inputs to output[i]
                # synthesize table transformation programs for each layer
                layer_candidate_progs = []
                for d in sym_data:

                    print("==> table synthesis input:")
                    #print(d.instantiate())
                    layer_candidate_progs.append(
                        synthesizer.enumerative_synthesis(
                            inputs, d.instantiate(), 
                            max_prog_size=config["max_prog_size"], 
                            time_limit_sec=config["time_limit_sec"],
                            solution_sketch_limit=config["solution_sketch_limit"],
                            solution_limit=config["solution_limit"],
                            disable_provenance_analysis=config["disable_provenance_analysis"]))
            
                # iterating over combinations for different layers
                layer_id_lists = [list(range(len(l))) for l in layer_candidate_progs]
                for layer_id_choices in itertools.product(*layer_id_lists):

                    #layer_prog[i] is the transformation program for the i-th layer
                    progs = [layer_candidate_progs[i][layer_id_choices[i]] for i in range(len(layer_id_choices))]

                    # apply each program on inputs to get output table for each layer
                    outputs = [p.eval(inputs).to_dict(orient="records") for p in progs]

                    all_field_mappings = [synth_utils.align_table_schema(sym_data[k].values, output, find_all_alignments=True) 
                            for k, output in enumerate(outputs)]

                    mapping_id_lists = [list(range(len(l))) for l in all_field_mappings]
                    for mapping_id_choices in itertools.product(*mapping_id_lists):

                        field_mappings = [all_field_mappings[i][idx] for i, idx in enumerate(mapping_id_choices)]
                        #print(field_mappings)

                        if config["vis_backend"] == "vegalite":
                            vis_design = VisDesign(data=outputs, chart=copy.deepcopy(chart))
                            vis_design.update_field_names(field_mappings)
                            candidates.append(([p.stmt_string() for p in progs], vis_design))
                        else:
                            vis_design = MatplotlibChart(outputs,copy.deepcopy(chart))
                            candidates.append(([p.stmt_string() for p in progs], vis_design.to_string_spec(field_mappings)))

            if len(candidates) > 0: break

        if group_results:
            return FalxEvalInterface.group_results(candidates)

        return candidates

EVAL_DIR = "../../benchmarks"


def run_synthesis(benchmark_path, num_samples, config):

    with open(benchmark_path, "r") as f:
        data = json.load(f)

    print("# run synthesize {}".format(benchmark_path))

    input_data = data["input_data"]
    vis = VisDesign.load_from_vegalite(data["vl_spec"], data["output_data"])
    full_trace = vis.eval()

    if "constants" in data:
        config["grammar"]["constants"] = data["constants"] 

    abstract_designs = VisDesign.inv_eval(full_trace)

    candidates = FalxEvalInterface.synthesize([input_data], full_trace, num_samples, group_results=True, config=config)

    return candidates


if __name__ == '__main__':

    config = {
        # configurations related to table transformation program synthesizer
        "solution_sketch_limit": 3,
        "solution_limit": 5,
        "time_limit_sec": 300,
        "max_prog_size": 2,

        "grammar": {
            "operators": ["select", "unite", "filter", "separate", "spread", 
                "gather", "gather_neg", "group_sum", "cumsum", "mutate", "mutate_custom"],
            "filer_op": [">", "<", "=="],
            "constants": [],
            "aggr_func": ["mean", "sum", "count"],
            "mutate_op": ["+", "-"],
            "gather_max_val_list_size": 6,
            "gather_max_key_list_size": 6,
            "consider_non_consecutive_gather_keys": False
        },

        "disable_provenance_analysis": False,

        # set the visualization backend, one of "vegalite, ggplot2, matplotlib"
        # ggplot2 and matplotlib have some feature restrictions
        "vis_backend": "vegalite"
    }

    for fname in os.listdir(EVAL_DIR):
        if fname.endswith("json") and "discard" not in fname:
            fpath = os.path.join(EVAL_DIR, fname)
            print("===================================")
            print(fpath)
            candidates = run_synthesis(fpath, 4, config)
            #print(len(candidates))
            for key, p in candidates.items():
                print(p)
