import sys

from io import StringIO 
import json
import numpy as np
from timeit import default_timer as timer
import subprocess

from symbolic import SymTable


def sample_symbolic_table(symtable, size, strategy="diversity"):
    """given a symbolic table, sample a smaller symbolic table that is contained by it
    Args:
        symtable: the input symbolic table
        size: the number of rows we want for the output table.
    Returns:
        the output table sample
    """
    if size > len(symtable.values):
        size = len(symtable.values)

    if strategy == "uniform":
        chosen_indices = np.random.choice(list(range(len(symtable.values))), size, replace=False)
    elif strategy == "diversity":
        indices = set(range(len(symtable.values)))
        chosen_indices = set()
        for i in range(size):
            pool = indices - chosen_indices
            candidate_size = min([20, len(pool)])
            candidates = np.random.choice(list(pool), size=candidate_size, replace=False)
            index = pick_diverse_candidate_index(candidates, chosen_indices, symtable.values)
            chosen_indices.add(index)

    sample_values = [symtable.values[i] for i in chosen_indices]
    symtable_sample = SymTable(sample_values)
    return symtable_sample


def pick_diverse_candidate_index(candidate_indices, chosen_indices, full_table):
    """according to current_chosen_row_indices and the full table, 
       choose the best candidate that maximize """
    keys = list(full_table[0].keys())
    cardinality = [len(set([r[key] for r in full_table])) for key in keys]
    def card_score_func(card_1, card_2):
        if card_1 == 1 and card_2 > 1:
            return 0
        return 1
    scores = []
    for x in candidate_indices:
        temp_card = [len(set([full_table[i][key] for i in list(chosen_indices) + [x]])) for key in keys]
        score = sum([card_score_func(temp_card[i], cardinality[i]) for i in range(len(keys))])
        scores.append(score)
    return candidate_indices[np.argmax(scores)]


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


def run_synthesis(fpath, num_samples):
    with open(fpath, "r") as f:
        data = json.load(f)

    print("# run synthesize {}".format(fpath.split('/')[-1]))

    input_data = data["input_data"]
    vis = VisDesign.load_from_vegalite(data["vl_spec"], data["output_data"])
    trace = vis.eval()    
    result = FalxEvalInterface.synthesize(inputs=[input_data], full_trace=trace, num_samples=num_samples)
    print("====>")
    for p, vis in result:
        print("# table_prog:")
        print("  {}".format(p))
        print("# vis_spec:")
        vl_obj = vis.to_vl_obj()
        data = vl_obj.pop("data")["values"]
        print("    {}".format(vl_obj))

def run_wrapper(fname, num_samples=4):
    print("\n====> {}".format(fname))
    with Capturing() as output:
        try:
            run_synthesis(fname, num_samples)
        except:
            pass
    print_flag = False
    for l in output:
        if print_flag:
            print(l)
        if "[info] #Candidates before getting the correct solution:" in l:
            print(l)
        if "====>" in l:
            print_flag = True

if __name__ == '__main__':
    run_synthesis("../benchmarks/001.json", 4)