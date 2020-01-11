import unittest

from falx.synthesizer.tidyverse import *
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

class TestTableLang(unittest.TestCase):

    def test_select(self):
        q = Table.from_dict(test_data)
        q = Select(q, [0, 1])
        print("---")
        for s in statements_to_string(q.to_stmts()):
            print(s)
        #print(q.eval())

    def test_unite(self):
        q = Table.from_dict(test_data)
        q = Unite(q, 1, 2)
        print("---")
        for s in statements_to_string(q.to_stmts()):
            print(s)
        #print(q.eval())

    def test_filter(self):
        q = Table.from_dict(test_data)
        q = Filter(q, 0, "==", 7)
        print("---")
        for s in statements_to_string(q.to_stmts()):
            print(s)
        #print(q.eval())

    def test_separate(self):
        q = Table.from_dict(test_data)
        q = Filter(q, 0, "==", 7)
        q = Unite(q, 1, 2)
        q = Separate(q, 3)
        print("---")
        for s in statements_to_string(q.to_stmts()):
            print(s)
        #print(q.eval())

    def test_spread(self):
        q = Table.from_dict(test_data)
        q = Select(q, [1, 2, 3])
        q = Spread(q, 1, 2)
        t = q.eval().reset_index()
        print("---")
        for s in statements_to_string(q.to_stmts()):
            print(s)
        #print(q.eval())

    def test_gather(self):
        q = Table.from_dict(test_data)
        q = Select(q, [1, 2, 3])
        q = Spread(q, 1, 2)
        q = Gather(q, [1, 2])
        t = q.eval().reset_index()
        print("---")
        for s in statements_to_string(q.to_stmts()):
            print(s)
        #print(q.eval())

    def test_gather_neg(self):
        q = Table.from_dict(test_data)
        q = Select(q, [1, 2, 3])
        q = Spread(q, 1, 2)
        q = GatherNeg(q, [0])
        print("---")
        for s in statements_to_string(q.to_stmts()):
            print(s)
        #print(q.eval())

    def test_cumsum(self):
        q = Table.from_dict(test_data)
        q = Select(q, [1, 2, 3])
        q = Filter(q, 1, "==", "alpha")
        q = CumSum(q, 3)
        print("---")
        for s in statements_to_string(q.to_stmts()):
            print(s)
        #print(q.eval())

    def test_mutate(self):
        q = Table.from_dict(test_data)
        q = Select(q, [1, 2, 3])
        q = Filter(q, 1, "==", "alpha")
        q = CumSum(q, 3)
        q = Mutate(q, 4, "-", 3)
        print("---")
        for s in statements_to_string(q.to_stmts()):
            print(s)
        #print(q.eval())

    def test_mutate_custom(self):
        q = Table.from_dict(test_data)
        q = Select(q, [1, 2, 3])
        q = MutateCustom(q, 1, "==", "alpha")
        print("---")
        for s in statements_to_string(q.to_stmts()):
            print(s)
        #print(q.eval())

if __name__ == '__main__':
    unittest.main()