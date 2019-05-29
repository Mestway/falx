import os
import operator
from collections import namedtuple
import itertools

from table import Table
from sql import *

class BVTable(SQL):
    def __init__(self, base_table, bv):
        """a bv representation of table """
        assert(len(base_table.values) == len(bv))
        self.base_table = base_table
        self.bv = bv

    def get_schema(self):
        return (self.base_table.name, self.base_table.fields)

    def eval(self):
        return [r for i, r in enumerate(self.base_table.values) if self.bv[i]]


class Enumerator(object):
    def __init__(self, resource=None):
        if resource is None:
            # default enumeration resource
            resource = {
                "aggr_funcs": [
                    sum, min, max,
                    lambda l: float(sum(l)) / len(l), # avg
                    lambda l: len(l), # count
                    lambda l: len(set(l)), # count disctinct
                ],
                "constants": []
            }
        self.resource = resource

    def enum_compare_ops(self):
        return [operator.lt, operator.le, operator.eq, 
                operator.ne, operator.ge, operator.gt]

    def enum_abs_select(self, tables):
        for t in tables:
            yield AbsSelect(t)

    def enum_abs_join(self, tables):
        for i in range(len(tables)):
            for j in range(i, len(tables)):
                yield AbsJoin(tables[i], tables[j])

    def enum_abs_aggr(self, tables):
        """enumerate abstract aggr queries from given tables """
        res = []
        for table in tables:
            fields = table.get_qualified_fields()
            table_content = table.eval()

            # find non-trivial gb keys, starting from empty gb_key
            keys = [[]]
            for gb_key_size in range(1, len(fields) - 1):
                last_size_keys = [key for key in keys if len(key) == gb_key_size - 1]
                for key_prefix in last_size_keys:
                    starting_index = 0 if key_prefix == [] else (key_prefix[-1] + 1)
                    for idx in range(starting_index):
                        new_key = key_prefix + [idx]
                        # check if the grouping is trivial: i.e., each row is in its own group
                        key_vals = [tuple([r[k] for k in new_key]) for r in table_content]
                        if len(key_vals) > len(set(key_vals)):
                            # this means the partition is not trivial
                            keys.append(new_key)

            # infer partition key
            for gb_key_index in keys:
                potential_targets = [idx for idx in range(len(fields)) 
                                        if idx not in gb_key_index]
                gb_fields = [ColRef(fields[i]) for i in gb_key_index]
                for target_index in potential_targets:
                    for aggr_func in self.resource["aggr_funcs"]:
                        new_name = "a1-{}".format(fields[target_index].split(".")[-1])
                        abs_q = AbsAggr(table, gb_fields, targets=[(aggr_func, ColRef(fields[target_index]), new_name)])
                        res.append(abs_q)
        return res

    def enum_union(self, inputs):
        for i in range(len(tables)):
            schema1 = tables[i].get_qualified_fields()
            for j in range(i, len(tables)):
                schema2 = tables[j].get_qualified_fields()
                if len(schema1) == len(schema2):
                    yield AbsUnion(tables[i], tables[j])

    def enum_left_join(self, inputs):
        for i in range(len(tables)):
            for j in range(i, len(tables)):
                yield AbsLeftJoin(tables[i], tables[j])

    def enum_basic_pred(self, left_vals, right_vals, ops):
        for lv in left_vals:
            for rv in right_vals:
                for op in ops:
                    yield BasicPred(op, lv, rv)
