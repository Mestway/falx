import json

from falx.chart import VisDesign
import morpheus
import itertools
from pprint import pprint

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
            if not isinstance(sym_data, (list,)):
                # single-layer chart
                candidate_progs = morpheus.synthesize(self.inputs, sym_data)
                for p in candidate_progs:
                    output = morpheus.evaluate(p, self.inputs)
                    vis_design = VisDesign(data=output, chart=chart)
                    candidates.append((p, vis_design))
            else: 
                # multi-layer charts
                # layer_candidate_progs[i] contains all programs that transform inputs to output[i]

                layer_candidate_progs = []
                for output in sym_data:
                    # synthesize table transformation programs
                    layer_candidate_progs.append(morpheus.synthesize(self.inputs, output))

                layer_id_lists = [list(range(len(l))) for l in layer_candidate_progs]
                
                # iterating over combinations for different layers
                for layer_id_choices in itertools.product(*layer_id_lists):

                    #layer_prog[i] is the transformation program for the i-th layer
                    progs = [layer_candidate_progs[i][layer_id_choices[i]] for i in range(len(layer_id_choices))]

                    # apply each program on inputs to get output table for each layer
                    outputs = [morpheus.evaluate(p, self.inputs) for p in progs]

                    vis_design = VisDesign(data=outputs, chart=chart)
                    candidates.append((progs, vis_design))

        return candidates
