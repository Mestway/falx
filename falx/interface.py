import json

from falx.chart import VisDesign
import morpheus_enumerator
import itertools

class FalxTask(object):

    def __init__(self, inputs, vtrace):
        self.inputs = inputs
        self.vtrace = vtrace

    def synthesize(self):
        """synthesize table prog and vis prog from input and output traces"""
        candidates = []

        # apply inverse semantics to obtain symbolic output table and vis programs
        abstract_designs = VisDesign.inv_eval(self.vtrace)

        for sym_data, chart in abstract_designs:

            # there could be multiple output tables for multi-layered charts
            # candidates_per_layer[i] contains all programs that transforms inputs to output[i]

            candidates_per_layer = []

            sym_tables = sym_data if isinstance(sym_data, (list,)) else [sym_data]
            for output in sym_tables:
                # synthesize table transformation programs
                candidates_per_layer.append(morpheus_enumerator.synthesize(self.inputs, output))

            num_candidates_per_layer = [list(range(len(l))) for l in candidates_per_layer]
            
            # iterating over combinations for different layers
            for id_list in itertools.product(*num_candidates_per_layer):
                progs_per_layer = [candidates[i][id_list[i]] for i in range(len(id_list))]

                # apply each program on inputs to get output table for each layer
                outputs = [morpheus_enumerator.evalute(p, self.inputs) for p in progs_per_layer]

                data = outputs[0] if len(outputs) == 1 else outputs
                prog = progs_per_layer[0] if len(progs_per_layer) == 1 else progs_per_layer

                vis_design = VisDesign(data=data, chart=chart)
                candidates.append((prog, vis_design))

        return candidates
