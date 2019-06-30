import json

from falx.chart import VisDesign
import morpheus
import itertools
from pprint import pprint
import numpy as np

def align_table_schema(table1, table2):
    """align table schema, assume that table1 is contained by table2"""
    assert(len(table1) <= len(table2))
    
    mapping = {}
    for k1 in table1[0].keys():
        mapping[k1] = []
        vals1 = [r[k1] for r in table1]
        for k2 in table2[0].keys():
            vals2 = [r[k2] for r in table2]
            l1 = np.array(sorted(vals1))
            l2 = np.array(sorted(vals2))
            if l1.dtype == l2.dtype and all(l1 == l2):
                mapping[k1].append(k2)
            elif l1.dtype == np.float64 and l2.dtype == np.float64:
                if np.allclose(l1, l2): 
                    mapping[k1].append(k2)                  

    # distill plausible mappings from the table
    # not all choices generated from the approach above generalize, we need to check consistency
    t1_schema = list(mapping.keys())
    mapping_id_lists = [list(range(len(mapping[key]))) for key in t1_schema]

    all_choices = list(itertools.product(*mapping_id_lists))

    # directly return if there is only one choice
    if len(all_choices) == 1:
        return {key:mapping[key][0] for key in mapping}

    assert("[align table] unimplemented error")
    for mapping_id_choices in all_choices:
        # the following is an instantiation of the the mapping
        inst = { t1_schema[i]:mapping[t1_schema[i]][mapping_id_choices[i]] for i in range(len(t1_schema))}

        # distill the tables for checking
        frozen_table1 = [tuple([r[key] for key in t1_schema]) for r in table1]
        frozen_table2 = [tuple([r[inst[key]] for key in t1_schema]) for r in table2]

        if all([frozen_table1.count(t) <= frozen_table2.count(t) for t in frozen_table1]):
            return inst
            
    return None


class Falx(object):

    @staticmethod
    def synthesize(inputs, vtrace, top_k=1):
        """synthesize table prog and vis prog from input and output traces"""
        candidates = []

        # apply inverse semantics to obtain symbolic output table and vis programs
        abstract_designs = VisDesign.inv_eval(vtrace)

        # sort pairs based on complexity of tables
        abstract_designs.sort(key=lambda x: len(x[0].values[0]) if not isinstance(x[0], (list,)) else sum([len(y.values[0]) for y in x[0]]))

        for sym_data, chart in abstract_designs:
            if not isinstance(sym_data, (list,)):
                # single-layer chart
                candidate_progs = morpheus.synthesize(inputs, sym_data)

                for p in candidate_progs:
                    output = morpheus.evaluate(p, inputs)

                    # print("******######******")
                    # pprint(sym_data.values)
                    # print("---")
                    # pprint(output)
                    
                    field_mapping = align_table_schema(sym_data.values, output)
                    assert(field_mapping != None)

                    vis_design = VisDesign(data=output, chart=chart)
                    vis_design.update_field_names(field_mapping)

                    candidates.append((p, vis_design))
                    
                    if len(candidates) >= top_k: break

            else:
                # multi-layer charts
                # layer_candidate_progs[i] contains all programs that transform inputs to output[i]
                 # synthesize table transformation programs for each layer
                layer_candidate_progs = [morpheus.synthesize(inputs, output) for output in sym_data]
                   
                # iterating over combinations for different layers
                layer_id_lists = [list(range(len(l))) for l in layer_candidate_progs]
                for layer_id_choices in itertools.product(*layer_id_lists):

                    #layer_prog[i] is the transformation program for the i-th layer
                    progs = [layer_candidate_progs[i][layer_id_choices[i]] for i in range(len(layer_id_choices))]

                    # apply each program on inputs to get output table for each layer
                    outputs = [morpheus.evaluate(p, inputs) for p in progs]

                    field_mappings = [align_table_schema(sym_data[k].values, output) for k, output in enumerate(outputs)]

                    vis_design = VisDesign(data=outputs, chart=chart)
                    vis_design.update_field_names(field_mappings)
                    candidates.append((progs, vis_design))

                    if len(candidates) >= top_k: break

            if len(candidates) >= top_k: break

        return candidates
