import sys

from io import StringIO 
import json
import numpy as np
from timeit import default_timer as timer
import subprocess

from falx.symbolic import SymTable


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