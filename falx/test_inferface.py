import unittest

from falx.chart import *
from falx.interface import *

class TestFalxInterface(unittest.TestCase):

    def test_line_chart_1(self):

        inputs = [[
            {"Totals":7,"Value":"A","variable":"alpha","value":2,"cumsum":2},
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
            {"Totals":9,"Value":"E","variable":"gamma","value":2,"cumsum":9}
        ]]

        vtrace = [
            Line(x1='A', y1=2, x2='B', y2=3, size=None, color='beta', column=None), 
            Line(x1='B', y1=3, x2='C', y2=3, size=None, color='beta', column=None), 
            Line(x1='A', y1=3, x2='B', y2=3, size=None, color='gamma', column=None),  
            Line(x1='B', y1=3, x2='C', y2=3, size=None, color='gamma', column=None), 
            Line(x1='C', y1=3, x2='D', y2=2, size=None, color='gamma', column=None),
            Line(x1='D', y1=3, x2='E', y2=4, size=None, color='alpha', column=None)
        ]

        candidates = Falx.synthesize(inputs=inputs, vtrace=vtrace)

        for ptable, vis_design in candidates:
            print(ptable)
            print(vis_design.to_vl_json())

    def test_line_chart_2(self):

        inputs = [[
            {"Year":1950,"Crustaceans":58578630,"Cod":2716706,"Tuna":69690537,"Herring":87161396,"Scorpion.fishes":15250015},
            {"Year":1951,"Crustaceans":59194582,"Cod":3861166,"Tuna":34829755,"Herring":51215349,"Scorpion.fishes":15454659},
            {"Year":1952,"Crustaceans":47562941,"Cod":4396174,"Tuna":31061481,"Herring":13962479,"Scorpion.fishes":12541484},
            {"Year":1953,"Crustaceans":68432658,"Cod":3901176,"Tuna":23225423,"Herring":13229061,"Scorpion.fishes":9524564},
            {"Year":1954,"Crustaceans":64395489,"Cod":4412721,"Tuna":20798126,"Herring":25285539,"Scorpion.fishes":9890656},
            {"Year":1955,"Crustaceans":76111004,"Cod":4774045,"Tuna":13992697,"Herring":18910756,"Scorpion.fishes":8446391}
        ]]

        vtrace = [
            Line(x1=1950, y1=58578630, x2=1951, y2=59194582, size=None, color='Crustaceans', column=None), 
            Line(x1=1954, y1=4412721, x2=1955, y2=4774045, size=None, color='Cod', column=None),
        ]

        candidates = Falx.synthesize(inputs=inputs, vtrace=vtrace)

        for ptable, vis_design in candidates:
            print(ptable)
            print(vis_design.to_vl_json())


if __name__ == '__main__':
    unittest.main()
