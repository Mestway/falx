import unittest

from falx.chart import *
from falx.interface_deprecated import *

class TestFalxInterface(unittest.TestCase):

    @unittest.skip
    def test_line_chart_1(self):

        inputs = [[
          { "Bucket": "Bucket E", "Budgeted": 100, "Actual": 115 },
          { "Bucket": "Bucket D", "Budgeted": 100, "Actual": 90 },
          { "Bucket": "Bucket C", "Budgeted": 125, "Actual": 115 },
          { "Bucket": "Bucket B", "Budgeted": 125, "Actual": 140 },
          { "Bucket": "Bucket A", "Budgeted": 140, "Actual": 150 }
        ]]

        vtrace = [
          {"type": "bar", "props": { "x": "Actual", "y": 115,  "color": "Actual", "x2": "", "y2": "", "column": "Bucket E"}},
          {"type": "bar", "props": { "x": "Actual", "y": 90,"color": "Actual", "x2": "", "y2": "", "column": "Bucket D"}},
          {"type": "bar", "props": { "x": "Budgeted","y": 100,  "color": "Budgeted", "x2": "", "y2": "", "column": "Bucket D"}},
        ]

        candidates = FalxInterface.synthesize(inputs=inputs, raw_trace=vtrace)

        for ptable, vis_design in candidates:
            print(ptable)
            print(vis_design.to_vl_json())

    def test_line_chart_2(self):

        inputs = [[
          {"Value":"means","Y1":0.52,"Y2":0.57,"Y3":0.6,"Y4":0.63,"Y5":0.63},
          {"Value":"stddev","Y1":0.1328,"Y2":0.1321,"Y3":0.1303,"Y4":0.1266,"Y5":0.1225},
          {"Value":"upper range","Y1":0.66,"Y2":0.7,"Y3":0.73,"Y4":0.75,"Y5":0.75},
          {"Value":"lower range","Y1":0.39,"Y2":0.44,"Y3":0.47,"Y4":0.5,"Y5":0.51}
        ]]

        vtrace = [
          {"type": "area", "props": {"x_left": "Y1", "y_top_left": 0.66, "y_bot_left": 0.39,  
                                     "x_right": "Y2", "y_top_right": 0.7, "y_bot_right": 0.44, "color": "", "column": ""}},
          {"type": "line", "props": {"x1": "Y1", "y1": 0.52, "x2": "Y2", "y2": 0.57, "color": "", "column": ""}},
          {"type": "line", "props": {"x1": "Y2", "y1": 0.57, "x2": "Y3", "y2": 0.6, "color": "", "column": ""}}
        ]

        candidates = FalxInterface.synthesize(inputs=inputs, raw_trace=vtrace)

        for ptable, vis_design in candidates:
            print(ptable)
            print(json.dumps(json.loads(vis_design.to_vl_json())))


if __name__ == '__main__':
    unittest.main()
