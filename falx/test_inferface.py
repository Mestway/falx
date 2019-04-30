import unittest

from falx.chart import *
from falx.interface import *

class TestFalxInterface(unittest.TestCase):

    def test_line_chart(self):

        inputs = [[{"Totals":7,"Value":"A","variable":"alpha","value":2,"cumsum":2},
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
                   {"Totals":9,"Value":"E","variable":"gamma","value":2,"cumsum":9}]]

        vtrace = [Line(x1='A', y1=2, x2='B', y2=3, size=None, color='beta', column=None), 
                  Line(x1='B', y1=3, x2='C', y2=3, size=None, color='beta', column=None), 
                  Line(x1='A', y1=3, x2='B', y2=3, size=None, color='gamma', column=None),  
                  Line(x1='B', y1=3, x2='C', y2=3, size=None, color='gamma', column=None), 
                  Line(x1='C', y1=3, x2='D', y2=2, size=None, color='gamma', column=None),
                  Line(x1='D', y1=3, x2='E', y2=4, size=None, color='alpha', column=None)]

        task = FalxTask(inputs=inputs, vtrace=vtrace)
        candidates = task.synthesize()

        for ptable, vis_design in candidates:
            print(ptable)
            print(vis_design.to_vl_json())

if __name__ == '__main__':
    unittest.main()
