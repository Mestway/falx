import json

from falx.chart import VisDesign
from falx.matplotlib_chart import MatplotlibChart

from tyrell.logger import get_logger

import morpheus
import itertools
from pprint import pprint
import numpy as np
import visual_trace
import copy

import synth_utils
import eval_utils

from pprint import pprint

np.random.seed(2019)

logger = get_logger("interface")
logger.setLevel('INFO')

class FalxInterface(object):

    # the default confifguration for the synthesizer
    default_config = {
        # configurations related to table transformation program synthesizer
        "solution_limit": 10,
        "time_limit_sec": 30,
        "search_start_depth_level": 1,
        "search_stop_depth_level": 2,
        "grammar_base_file": "dsl/tidyverse.tyrell.base",

        # the following two criterias defines restrictions on which sketches / program symbols 
        # can be used during the synthesis process
        "sketch_restriction": None,
        "component_restriction": None,

        # set the visualizatino backend, one of "vegalite, ggplot2, matplotlib"
        # ggplot2 and matplotlib have some feature restrictions
        "vis_backend": "vegalite"
    }

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

    def update_config(user_config):
        config = copy.copy(FalxInterface.default_config)
        for key in user_config:
            if key in config:
                config[key] = user_config[key]
            else:
                logger.warning(f"[] Key {key} is not part of the synthesizer config.")

        assert config["vis_backend"] in ["vegalite", "matplotlib"]
        assert config["solution_limit"] >= 1
        assert config["time_limit_sec"] > 0
        assert config["search_start_depth_level"] >= 1
        assert config["search_stop_depth_level"] >= config["search_start_depth_level"]

        return config

    @staticmethod
    def synthesize(inputs, raw_trace, extra_consts=[], group_results=False, config={}):
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
                    { "solution_limit": ..., "time_limit_sec": ...,
                      "starting_search_program_length": 1, "stop_search_program_length": 2,
                      "grammar_base_file": "dsl/tidyverse.tyrell.base",
                      "block_sketches": [], "block_program_symbols": [], "vis_backend": "vegalite" }
        """

        # update synthesizer config
        config = FalxInterface.update_config(config)

        example_trace = visual_trace.load_trace(raw_trace)

        # apply inverse semantics to obtain symbolic output table and vis programs
        abstract_designs = None
        if config["vis_backend"] == "vegalite":
            abstract_designs = VisDesign.inv_eval(example_trace)  
        else:
            abstract_designs = MatplotlibChart.inv_eval(example_trace)
        
        # sort pairs based on complexity of tables
        abstract_designs.sort(key=lambda x: len(x[0].values[0]) 
                                if not isinstance(x[0], (list,)) else sum([len(y.values[0]) for y in x[0]]))

        logger.info("# Synthesizer configuration")
        logger.info(json.dumps(config, indent=2))

        candidates = []
        for sym_data, chart in abstract_designs:
            # split case based on single layered chart or multi layered chart
            if not isinstance(sym_data, (list,)):
                # single-layer chart
                candidate_progs = morpheus.synthesize(
                    inputs, sym_data, 
                    extra_consts=extra_consts, oracle_output=None, 
                    prune="falx",  grammar_base_file=config["grammar_base_file"],
                    solution_limit=config["solution_limit"], 
                    time_limit_sec=config["time_limit_sec"], 
                    search_start_depth_level=config["search_start_depth_level"],
                    search_stop_depth_level=config["search_stop_depth_level"],
                    component_restriction=config["component_restriction"],
                    sketch_restriction=config["sketch_restriction"])

                for p in candidate_progs:
                    output = morpheus.evaluate(p, inputs)

                    field_mapping = synth_utils.align_table_schema(sym_data.values, output)
                    assert(field_mapping != None)

                    if config["vis_backend"] == "vegalite":
                        vis_design = VisDesign(data=output, chart=copy.deepcopy(chart))
                        vis_design.update_field_names(field_mapping)
                        candidates.append((p, vis_design))
                    else:
                        vis_design = MatplotlibChart(output, copy.deepcopy(chart))
                        candidates.append((p, vis_design.to_string_spec(field_mapping)))
            else:
                # multi-layer charts
                # layer_candidate_progs[i] contains all programs that transform inputs to output[i]
                # synthesize table transformation programs for each layer
                layer_candidate_progs = [morpheus.synthesize(
                                            inputs, d, extra_consts=extra_consts, oracle_output=None, 
                                            prune="falx", grammar_base_file=config["grammar_base_file"],
                                            solution_limit=config["solution_limit"], 
                                            time_limit_sec=config["time_limit_sec"], 
                                            search_start_depth_level=config["search_start_depth_level"],
                                            search_stop_depth_level=config["search_stop_depth_level"],
                                            component_restriction=config["component_restriction"],
                                            sketch_restriction=config["sketch_restriction"]) for d in sym_data]

                # iterating over combinations for different layers
                layer_id_lists = [list(range(len(l))) for l in layer_candidate_progs]
                for layer_id_choices in itertools.product(*layer_id_lists):

                    #layer_prog[i] is the transformation program for the i-th layer
                    progs = [layer_candidate_progs[i][layer_id_choices[i]] for i in range(len(layer_id_choices))]

                    # apply each program on inputs to get output table for each layer
                    outputs = [morpheus.evaluate(p, inputs) for p in progs]

                    field_mappings = [synth_utils.align_table_schema(sym_data[k].values, output) for k, output in enumerate(outputs)]

                    print(field_mappings)

                    if config["vis_backend"] == "vegalite":
                        vis_design = VisDesign(data=outputs, chart=copy.deepcopy(chart))
                        vis_design.update_field_names(field_mappings)
                        candidates.append((progs, vis_design))
                    else:
                        vis_design = MatplotlibChart(outputs,copy.deepcopy(chart))
                        candidates.append((progs, vis_design.to_string_spec(field_mappings)))

            if len(candidates) > 0: break

        if group_results:
            return FalxInterface.group_results(candidates)
        return candidates

if __name__ == '__main__':

    input_data = [
      { "Bucket": "Bucket E", "Budgeted": 100, "Actual": 115 },
      { "Bucket": "Bucket D", "Budgeted": 100, "Actual": 90 },
      { "Bucket": "Bucket C", "Budgeted": 125, "Actual": 115 },
      { "Bucket": "Bucket B", "Budgeted": 125, "Actual": 140 },
      { "Bucket": "Bucket A", "Budgeted": 140, "Actual": 150 }
    ]

    raw_trace = [
      {"type": "bar", "props": { "x": "Actual", "y": 115,  "color": "Actual", "x2": "", "y2": "", "column": "Bucket E"}},
      {"type": "bar", "props": { "x": "Actual", "y": 90,"color": "Actual", "x2": "", "y2": "", "column": "Bucket D"}},
      {"type": "bar", "props": { "x": "Budgeted","y": 100,  "color": "Budgeted", "x2": "", "y2": "", "column": "Bucket D"}},
    ]

    result = FalxInterface.synthesize(inputs=[input_data], raw_trace=raw_trace, extra_consts=[], group_results=True)

    for val in result:
        print("#####")
        print(val)
        for p in result[val]:
            print(p[0])
            #print(p[1].to_vl_json())

        