import json

from falx.chart import VisDesign
from falx.matplotlib_chart import MatplotlibChart

import morpheus
import itertools
from pprint import pprint
import numpy as np
import visual_trace

import synth_utils
import eval_utils

from pprint import pprint

np.random.seed(2019)

class FalxInterface(object):

    @staticmethod
    def synthesize(inputs, raw_trace, extra_consts=[], 
                   backend="vegalite", grammar_base_file="dsl/tidyverse.tyrell.base"):
        """synthesize table prog and vis prog from input and output traces"""

        assert backend == "vegalite" or backend == "matplotlib"

        example_trace = visual_trace.load_trace(raw_trace)

        candidates = []

        # apply inverse semantics to obtain symbolic output table and vis programs
        abstract_designs = VisDesign.inv_eval(example_trace) if backend == "vegalite" else MatplotlibChart.inv_eval(example_trace)

        # sort pairs based on complexity of tables
        abstract_designs.sort(key=lambda x: len(x[0].values[0]) if not isinstance(x[0], (list,)) else sum([len(y.values[0]) for y in x[0]]))

        for sym_data, chart in abstract_designs:

            if not isinstance(sym_data, (list,)):
                # single-layer chart
                candidate_progs = morpheus.synthesize(inputs, sym_data, oracle_output=None, 
                    prune="falx", extra_consts=extra_consts, grammar_base_file=grammar_base_file)

                for p in candidate_progs:
                    output = morpheus.evaluate(p, inputs)

                    field_mapping = synth_utils.align_table_schema(sym_data.values, output)
                    assert(field_mapping != None)

                    if backend == "vegalite":
                        vis_design = VisDesign(data=output, chart=chart)
                        vis_design.update_field_names(field_mapping)
                        candidates.append((p, vis_design))
                    else:
                        vis_design = MatplotlibChart(output,chart)
                        candidates.append((p, vis_design.to_string_spec(field_mapping)))

                    if len(candidates) > 0: break
            else:
                # multi-layer charts
                # layer_candidate_progs[i] contains all programs that transform inputs to output[i]
                # synthesize table transformation programs for each layer
 
                layer_candidate_progs = [morpheus.synthesize(inputs, d, oracle_output=None, 
                                            prune="falx", extra_consts=extra_consts, grammar_base_file=grammar_base_file) for d in sym_data]

                # iterating over combinations for different layers
                layer_id_lists = [list(range(len(l))) for l in layer_candidate_progs]
                for layer_id_choices in itertools.product(*layer_id_lists):

                    #layer_prog[i] is the transformation program for the i-th layer
                    progs = [layer_candidate_progs[i][layer_id_choices[i]] for i in range(len(layer_id_choices))]

                    # apply each program on inputs to get output table for each layer
                    outputs = [morpheus.evaluate(p, inputs) for p in progs]

                    field_mappings = [synth_utils.align_table_schema(sym_data[k].values, output) for k, output in enumerate(outputs)]

                    if backend == "vegalite":
                        vis_design = VisDesign(data=outputs, chart=chart)
                        vis_design.update_field_names(field_mappings)
                        candidates.append((progs, vis_design))
                    else:
                        vis_design = MatplotlibChart(outputs,chart)
                        candidates.append((progs, vis_design.to_string_spec(field_mappings)))
                    if len(candidates) > 0: break

            if len(candidates) > 0: break

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

    result = FalxInterface.synthesize(inputs=[input_data], raw_trace=raw_trace, extra_consts=[], backend="vegalite")

    for c in result:
        print(c[0])
        print(c[1].to_vl_json())

        