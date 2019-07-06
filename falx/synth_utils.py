import json
import itertools
import numpy as np

def construct_value_dict(values):
    values = np.array(values)
    try:
        values = values.astype(np.float64)
        values = np.round(values, 5)
    except:
        pass
    value_dict = {}
    for x in values:
        if not x in value_dict:
            value_dict[x] = 0
        value_dict[x] += 1
    return value_dict

def check_table_inclusion(table1, table2):
    """check table inclusion, this is sound but not complete: if it thinks two tbales are not equal, they absolutely inequal"""
    if len(table1) == 0:
        return True

    mapping = {}
    vals2_dicts = {}
    for k2 in table2[0].keys():
        vals2_dicts[k2] = construct_value_dict([r[k2] for r in table2 if k2 in r])
    for k1 in table1[0].keys():
        mapping[k1] = []
        vals1_dict = construct_value_dict([r[k1] for r in table1 if k1 in r])
        for k2 in table2[0].keys():
            vals2_dict = vals2_dicts[k2]
            contained = True
            for x in vals1_dict:
                if x not in vals2_dict:
                    contained = False
                if contained == False:
                    break
            if contained:
                mapping[k1].append(k2)

    # distill plausible mappings from the table
    # not all choices generated from the approach above generalize, we need to check consistency
    t1_schema = list(mapping.keys())
    mapping_id_lists = [list(range(len(mapping[key]))) for key in t1_schema]
    check_ok = all([len(l) > 0 for l in mapping_id_lists])
    return check_ok

def table_to_inv_map(table):
    """convert a table to an inverse map
    Args:
        table: a table (list of dicts) [{"c1":...}..]
    Returns:
        a map M that maps a value to all occurrences of the value in table 
        s.t. (i, c_j) in M[v] if table[i][c_j] = v
    """
    inv_map = {}
    for i, r in enumerate(table):
        for c, v in r.items():
            if v not in inv_map:
                inv_map[v] = []
            inv_map[v].append((i, c))
    return inv_map


def table_subset_eq_w_subst(table1, table2, mapping):
    """check whether table1 is subsumed by table2 
        Mapping is a list of tuples (col1, col2) 
        that maps columns in table1 to columns in table2
    """
    if len(table1) == 0: return True
    if len(table2) == 0: return False

    frozen_table1 = [tuple([t[m[0]] for m in mapping]) for t in table1]
    frozen_table2 = [tuple([t[m[1]] for m in mapping]) for t in table2]

    for t in frozen_table1:
        cnt1 = len([r for r in frozen_table1 if r == t])
        cnt2 = len([r for r in frozen_table2 if r == t])
        if cnt2 < cnt1:
            return False
    return True


def infer_projection(table1, table2):
    """given two tables table1, table2, 
       infer if it is possible to project and filter table2 to obtain table1
    """
    assert(len(table1) <= len(table2) and len(table1[0]) <= len(table2[0]))
    t2_inv_map = table_to_inv_map(table2)

    # find mappings from values in table1 to table2
    tr = {}
    for i, r in enumerate(table1):
        for c, v in r.items():
            if v not in t2_inv_map:
                # impossible to achieve
                return None
            tr[(i, c)] = t2_inv_map[v]

    # stores column destinations: for each col in table1, stores all possible cols in table2
    col_mapping = {}

    exists_updates = True
    while exists_updates:
        # alternating prune row and col, until we finalize
        exists_updates = False

        # entries from the same column in table1 should come from the same column in table2
        for c in table1[0].keys():
            col_dst = None
            for i in range(len(table1)):
                tmp_col_dst = [coord[1] for coord in tr[(i, c)]]
                # intersect to filter out invalid dsts (i.e., a dst that cannot satisfy both coords)
                col_dst = tmp_col_dst if col_dst == None else [x for x in col_dst if x in tmp_col_dst]
            col_mapping[c] = col_dst
            # exists no mapping
            if col_dst == []:
                return None
            for i in range(len(table1)):
                # remove dsts that are not in candidate dst
                new_dst = [coord for coord in tr[(i, c)] if coord[1] in col_dst]
                if len(new_dst) < len(tr[(i, c)]):
                    exists_updates = True
                tr[(i, c)] = new_dst

        for i in range(len(table1)):
            row_dst = None
            for c in table1[0].keys():
                tmp_row_dst = [coord[0] for coord in tr[(i, c)]]
                row_dst = tmp_row_dst if row_dst == None else [x for x in row_dst if x in tmp_row_dst]
            if row_dst == []:
                return None
            for c in table1[0].keys():
                # remove dsts that are not in candidt row dst
                new_dst = [coord for coord in tr[(i, c)] if coord[0] in row_dst]
                if len(new_dst) < len(tr[(i, c)]):
                    exists_updates = True
                tr[(i,c)] = new_dst

    keys = list(col_mapping.keys())
    vals = [col_mapping[key] for key in keys]
    all_mappings = []
    for targets in itertools.product(*vals):
        mapping = [(keys[i], targets[i])for i in range(len(keys))]
        if table_subset_eq_w_subst(table1, table2, mapping):
            all_mappings.append(mapping)

    return all_mappings


if __name__ == '__main__':
    table2 = [
            {"Totals":7,"Value":"A","variable":"alpha","value":2,"cumsum":2, "Value2":"A"},
            {"Totals":8,"Value":"B","variable":"alpha","value":2,"cumsum":2, "Value2":"B"},
            {"Totals":9,"Value":"C","variable":"alpha","value":3,"cumsum":3, "Value2":"C"},
            {"Totals":9,"Value":"D","variable":"alpha","value":3,"cumsum":3, "Value2":"D"},
            {"Totals":9,"Value":"E","variable":"alpha","value":4,"cumsum":4, "Value2":"E"},
            {"Totals":7,"Value":"A","variable":"beta","value":2,"cumsum":4, "Value2":"A"},
            {"Totals":8,"Value":"B","variable":"beta","value":3,"cumsum":5, "Value2":"B"},
            {"Totals":9,"Value":"C","variable":"beta","value":3,"cumsum":6, "Value2":"C"}, 
            {"Totals":9,"Value":"D","variable":"beta","value":4,"cumsum":7, "Value2":"D"},
            {"Totals":9,"Value":"E","variable":"beta","value":3,"cumsum":7, "Value2":"E"},
            {"Totals":7,"Value":"A","variable":"gamma","value":3,"cumsum":7, "Value2":"A"},
            {"Totals":8,"Value":"B","variable":"gamma","value":3,"cumsum":8, "Value2":"B"},
            {"Totals":9,"Value":"C","variable":"gamma","value":3,"cumsum":9, "Value2":"C"},
            {"Totals":9,"Value":"D","variable":"gamma","value":2,"cumsum":9, "Value2":"D"},
            {"Totals":9,"Value":"E","variable":"gamma","value":2,"cumsum":9, "Value2":"E"}
        ]

    table1 = [
            {"t":7,"Value":"A","value":2,"c":2},
            {"t":8,"Value":"B","value":2,"c":2},
            {"t":9,"Value":"C","value":3,"c":3},
            {"t":7,"Value":"A","value":3,"c":7},
            {"t":8,"Value":"B","value":3,"c":8},
            {"t":9,"Value":"C","value":3,"c":9},
            {"t":9,"Value":"D","value":2,"c":9},
            {"t":9,"Value":"E","value":2,"c":9}
        ]

    print(infer_projection(table1, table2))
