import json

from falx.chart import VisDesign
import morpheus
import itertools
from pprint import pprint
import numpy as np
import synth_utils

def align_table_schema(table1, table2, check_equivalence=False, boolean_result=False):
    """align table schema, assume that table1 is contained by table2"""
    if len(table1) > len(table2):
        # cannot find any mapping
        return None

    if boolean_result and len(table1) == 0:
        return True

    mapping = {}
    vals2_dicts = {}
    for k2 in table2[0].keys():
        vals2_dicts[k2] = synth_utils.construct_value_dict([r[k2] for r in table2 if k2 in r])
    for k1 in table1[0].keys():
        mapping[k1] = []
        vals1_dict = synth_utils.construct_value_dict([r[k1] for r in table1 if k1 in r])
        for k2 in table2[0].keys():
            vals2_dict = vals2_dicts[k2]
            contained = True
            for x in vals1_dict:
                if (x not in vals2_dict) or (vals2_dict[x] < vals1_dict[x]):
                    contained = False
                if check_equivalence and (x not in vals2_dict or vals2_dict[x] != vals1_dict[x]):
                    contained = False
                if contained == False:
                    break
            if contained and check_equivalence:
                for x in vals2_dict:
                    if x not in vals1_dict:
                        contained = False
                        break

            if contained:
                mapping[k1].append(k2)
    
    #print(mapping)

    # distill plausible mappings from the table
    # not all choices generated from the approach above generalize, we need to check consistency
    t1_schema = list(mapping.keys())
    mapping_id_lists = [list(range(len(mapping[key]))) for key in t1_schema]

    all_choices = list(itertools.product(*mapping_id_lists))

    if boolean_result: return len(all_choices) > 0

    # directly return if there is only one choice
    if len(all_choices) == 1:
        return {key:mapping[key][0] for key in mapping}

    #assert("[align table] unimplemented error")
    for mapping_id_choices in all_choices:
        # the following is an instantiation of the the mapping
        inst = { t1_schema[i]:mapping[t1_schema[i]][mapping_id_choices[i]] for i in range(len(t1_schema))}

        def value_handling_func(val):
            if isinstance(val, (int, str,)):
                return val
            try:
                val = float(val)
                val = np.round(val, 5)
            except:
                pass
            return val

        # distill the tables for checking
        frozen_table1 = [tuple([value_handling_func(r[key]) for key in t1_schema if key in r]) for r in table1]
        frozen_table2 = [tuple([value_handling_func(r[inst[key]]) for key in t1_schema if inst[key] in r]) for r in table2]

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


