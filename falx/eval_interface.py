import json

from falx.chart import VisDesign
import morpheus
import itertools
from pprint import pprint
import numpy as np
from symbolic import SymTable

import interface

def sample_symbolic_table(symtable, size=2):
    if size > len(symtable.values):
        size = len(symtable.values)
    rand_indices = np.random.choice(list(range(len(symtable.values))), size, replace=False)
    sample_values = [symtable.values[i] for i in rand_indices]
    symtable_sample = SymTable(sample_values)
    return symtable_sample


class FalxEvalInterface(object):

    @staticmethod
    def synthesize(inputs, full_trace, num_samples=2, top_k=1):
        """synthesize table prog and vis prog from input and output traces"""
        candidates = []

        # apply inverse semantics to obtain symbolic output table and vis programs
        abstract_designs = VisDesign.inv_eval(full_trace)

        # sort pairs based on complexity of tables
        abstract_designs.sort(key=lambda x: len(x[0].values[0]) if not isinstance(x[0], (list,)) else sum([len(y.values[0]) for y in x[0]]))

        for full_sym_data, chart in abstract_designs:

            if not isinstance(full_sym_data, (list,)):

                sample_output = sample_symbolic_table(full_sym_data, num_samples)

                # single-layer chart
                candidate_progs = morpheus.synthesize_with_oracle(inputs, sample_output, full_sym_data)

                for p in candidate_progs:
                    output = morpheus.evaluate(p, inputs)
                    
                    field_mapping = interface.align_table_schema(full_sym_data.values, output)
                    assert(field_mapping != None)

                    vis_design = VisDesign(data=output, chart=chart)
                    vis_design.update_field_names(field_mapping)

                    candidates.append((p, vis_design))
                    
                    if len(candidates) >= top_k: break
            else:
                # multi-layer charts
                # layer_candidate_progs[i] contains all programs that transform inputs to output[i]
                # synthesize table transformation programs for each layer
                sym_tables = [(sample_symbolic_table(full_output), full_output, num_samples) for full_output in full_sym_data]
                layer_candidate_progs = [morpheus.synthesize_with_oracle(inputs, p[0], p[1]) for p in sym_tables]
                   
                # iterating over combinations for different layers
                layer_id_lists = [list(range(len(l))) for l in layer_candidate_progs]
                for layer_id_choices in itertools.product(*layer_id_lists):

                    #layer_prog[i] is the transformation program for the i-th layer
                    progs = [layer_candidate_progs[i][layer_id_choices[i]] for i in range(len(layer_id_choices))]

                    # apply each program on inputs to get output table for each layer
                    outputs = [morpheus.evaluate(p, inputs) for p in progs]

                    field_mappings = [interface.align_table_schema(full_sym_data[k].values, output) for k, output in enumerate(outputs)]

                    vis_design = VisDesign(data=outputs, chart=chart)
                    vis_design.update_field_names(field_mappings)
                    candidates.append((progs, vis_design))

                    if len(candidates) >= top_k: break

            if len(candidates) >= top_k: break

        return candidates