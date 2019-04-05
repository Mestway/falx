import unittest
from falx.chart import LineChart, Encoding

class TestChart(unittest.TestCase):

    def test_gen_chart(self):
        line_chart = LineChart(
            enc_x = Encoding("x", "c1", "nominal"),
            enc_y = Encoding("y", "c2", "quantitative"))

        print(line_chart.to_vl_json())

if __name__ == '__main__':
    unittest.main()