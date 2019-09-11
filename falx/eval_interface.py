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

def check_trace_consistency(vis_prog, orig_trace):
    """check whether the prog is consistent with the full trace"""
    tr = vis_prog.eval()
    orig_tr_table = visual_trace.trace_to_table(orig_trace)
    new_tr_table = visual_trace.trace_to_table(tr)
    return all([synth_utils.align_table_schema(new_tr_table[key], orig_tr_table[key]) != None for key in new_tr_table])

class FalxEvalInterface(object):

    @staticmethod
    def synthesize(inputs, full_trace, num_samples=2, extra_consts=[], 
                   backend="vegalite", prune="falx", grammar_base_file="dsl/tidyverse.tyrell.base"):
        """synthesize table prog and vis prog from input and output traces"""
        assert backend == "vegalite" or backend == "matplotlib"
        assert prune == "falx" or prune == "morpheus" or prune == "forward" or prune == "none" or prune == "backward"
        candidates = []

        # apply inverse semantics to obtain symbolic output table and vis programs
        abstract_designs = VisDesign.inv_eval(full_trace) if backend == "vegalite" else MatplotlibChart.inv_eval(full_trace)

        # sort pairs based on complexity of tables
        abstract_designs.sort(key=lambda x: len(x[0].values[0]) if not isinstance(x[0], (list,)) else sum([len(y.values[0]) for y in x[0]]))

        for full_sym_data, chart in abstract_designs:

            if not isinstance(full_sym_data, (list,)):
                sample_output = eval_utils.sample_symbolic_table(full_sym_data, num_samples)

                # single-layer chart
                candidate_progs = morpheus.synthesize(inputs, sample_output, full_sym_data, prune, 
                                                        extra_consts=extra_consts, grammar_base_file=grammar_base_file)

                for p in candidate_progs:
                    #pprint(inputs[0])
                    output = morpheus.evaluate(p, inputs)

                    #print("===========> Synthesis output")
                    # pprint("====> table")
                    # pprint(output)
                    # print("---")
                    # pprint(full_sym_data.values)
                    # mapping = synth_utils.align_table_schema(full_sym_data.values, output)
                    # print(mapping)
                  
                    field_mapping = synth_utils.align_table_schema(full_sym_data.values, output)
                    assert(field_mapping != None)

                    if backend == "vegalite":
                        vis_design = VisDesign(data=output, chart=chart)
                        vis_design.update_field_names(field_mapping)
                        if check_trace_consistency(vis_design, full_trace):
                            candidates.append((p, vis_design))
                        else:
                            print("===> the program is not consistent with the trace")
                            print(" {}".format(p))
                            print("===> continue...")
                    else:
                        vis_design = MatplotlibChart(output,chart)
                        candidates.append((p, vis_design.to_string_spec(field_mapping)))

                    if len(candidates) > 0: break
            else:
                # multi-layer charts
                # layer_candidate_progs[i] contains all programs that transform inputs to output[i]
                # synthesize table transformation programs for each layer
                sym_tables = []
                for full_output in full_sym_data:
                    sample_table = eval_utils.sample_symbolic_table(full_output, num_samples)
                    sym_tables.append((sample_table, full_output))

                layer_candidate_progs = [morpheus.synthesize(inputs, p[0], p[1], prune, 
                                            extra_consts=extra_consts, grammar_base_file=grammar_base_file) for p in sym_tables]

                # iterating over combinations for different layers
                layer_id_lists = [list(range(len(l))) for l in layer_candidate_progs]
                for layer_id_choices in itertools.product(*layer_id_lists):

                    #layer_prog[i] is the transformation program for the i-th layer
                    progs = [layer_candidate_progs[i][layer_id_choices[i]] for i in range(len(layer_id_choices))]

                    # apply each program on inputs to get output table for each layer
                    outputs = [morpheus.evaluate(p, inputs) for p in progs]

                    # print("===========> Synthesis output")
                    # for i in range(len(outputs)):
                    #     pprint("====> table {}".format(i))
                    #     pprint(outputs[i])
                    #     print("---")
                    #     pprint(full_sym_data[i].values)
                    #     mapping = synth_utils.align_table_schema(full_sym_data[i].values, outputs[i])
                    #     print(mapping)

                    field_mappings = [synth_utils.align_table_schema(full_sym_data[k].values, output) for k, output in enumerate(outputs)]

                    if backend == "vegalite":
                        vis_design = VisDesign(data=outputs, chart=chart)
                        vis_design.update_field_names(field_mappings)
                        if check_trace_consistency(vis_design, full_trace):
                            candidates.append((progs, vis_design))
                        else:
                            print("===> the program is not consistent with the trace, continue")
                    else:
                        vis_design = MatplotlibChart(outputs,chart)
                        candidates.append((progs, vis_design.to_string_spec(field_mappings)))
                    if len(candidates) > 0: break

            if len(candidates) > 0: break

        return candidates