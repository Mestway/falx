from pprint import pprint
from falx.synthesizer.utils import HOLE

def disable_sketch(p):
    """check if the program sketch is a bad sketch, 
            we will prevent bad sketch directly """
    
    def get_op_list(_ast):
        return [_ast["op"]] + [v for c in _ast["args"] if c["type"] == "node" for v in get_op_list(c)]

    ast = p.to_dict()
    op_list = get_op_list(ast)

    if "select" in op_list or "filter" in op_list:
        # filter is currently disabled
        # select is implicitly used in visualization spec
        return True

    # group_sum and mutate_custom can only be used in the last operator
    if "group_sum" in op_list[1:] or "mutate_custom" in op_list[1:]: 
        return True
    
    # No more than 1 gather, no more than 1 mutate
    if len([s for s in op_list if s in ["gather", "gather_neg"]]) > 1:
        return True
    if len([s for s in op_list if s in ["mutate", "mutate_custom"]]) > 1:
        return True

    def contains_repetition(_ast, except_list):
        """check if there is a sketch that contains repetitive components """
        for child in _ast["args"]:
            if child["type"] == "node": 
                if (child["op"] == _ast["op"] and child["op"] not in except_list) or contains_repetition(child, except_list):
                    return True
        return False

    # No repetitive component except for separate.
    if contains_repetition(ast, except_list=["separate"]): return True

    return False