import unittest

from falx.table.language import *
import os

test_data = [{"Totals":7,"Value":"A","variable":"alpha","value":2,"cumsum":2},
             {"Totals":8,"Value":"B","variable":"alpha","value":2,"cumsum":2},
             {"Totals":9,"Value":"C","variable":"alpha","value":3,"cumsum":3},
             {"Totals":9,"Value":"D","variable":"alpha","value":3,"cumsum":3},
             {"Totals":9,"Value":"E","variable":"alpha","value":4,"cumsum":4},
             {"Totals":7,"Value":"A","variable":"beta","value":2,"cumsum":4},
             {"Totals":8,"Value":"B","variable":"beta","value":3,"cumsum":5},
             {"Totals":9,"Value":"C","variable":"beta","value":3,"cumsum":6},
             {"Totals":9,"Value":"D","variable":"beta","value":4,"cumsum":7},
             {"Totals":9,"Value":"E","variable":"beta","value":3,"cumsum":7},
             {"Totals":7,"Value":"A","variable":"gamma","value":3,"cumsum":7},
             {"Totals":8,"Value":"B","variable":"gamma","value":3,"cumsum":8},
             {"Totals":9,"Value":"C","variable":"gamma","value":3,"cumsum":9},
             {"Totals":9,"Value":"D","variable":"gamma","value":2,"cumsum":9},
             {"Totals":9,"Value":"E","variable":"gamma","value":2,"cumsum":9}]

inputs = {0: pd.DataFrame.from_dict(test_data)}

class TestTableLang(unittest.TestCase):
    
    def test_select(self):
        q = Table(data_id=0)
        q = Select(q, HOLE)
        print("---")
        print(q.stmt_string())
        print(q.is_abstract())
        print(q.eval(inputs=inputs) if not q.is_abstract() else "[Expression is abstract]")

    def test_group(self):
        q = Table(data_id=0)
        q = GroupSummary(q, [1], -1, "count")
        print("---")
        print(q.stmt_string())
        print(q.is_abstract())
        print(q.eval(inputs=inputs) if not q.is_abstract() else "[Expression is abstract]")

    def test_unite(self):
        q = Table(data_id=0)
        q = Unite(q, 1, 2)
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_filter(self):
        q = Table(data_id=0)
        q = Filter(q, 0, "==", 7)
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_separate(self):
        q = Table(data_id=0)
        q = Filter(q, 0, "==", 7)
        q = Unite(q, 1, 2)
        q = Separate(q, 3)
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_spread(self):
        q = Table(data_id=0)
        q = Select(q, [1, 2, 3])
        q = Spread(q, 1, 2)
        t = q.eval(inputs=inputs).reset_index()
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_gather(self):
        q = Table(data_id=0)
        q = Select(q, [1, 2, 3])
        q = Spread(q, 1, 2)
        q = Gather(q, [1, 2])
        print("---")
        print(q.stmt_string())
        print(q.eval(inputs=inputs) if not q.is_abstract() else "[Expression is abstract]")

    def test_gather_neg(self):
        q = Table(data_id=0)
        q = Select(q, [1, 2, 3])
        q = Spread(q, 1, 2)
        q = GatherNeg(q, [0])
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_cumsum(self):
        q = Table(data_id=0)
        q = Select(q, [1, 2, 3])
        q = Filter(q, 1, "==", "alpha")
        q = CumSum(q, 3)
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_mutate(self):
        q = Table(data_id=0)
        q = Select(q, [1, 2, 3])
        q = Filter(q, 1, "==", "alpha")
        q = CumSum(q, 3)
        q = Mutate(q, 4, "-", 3)
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_mutate_custom(self):
        q = Table(data_id=0)
        q = Select(q, [1, 2, 3])
        q = MutateCustom(q, 1, "==", "alpha")
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

if __name__ == '__main__':
    unittest.main()