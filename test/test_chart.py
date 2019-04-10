import unittest
from falx.chart import *

example_data = [{"Totals":7,"Value":"A","variable":"alpha","value":2,"cumsum":2},
                {"Totals":8,"Value":"B","variable":"alpha","value":2,"cumsum":2},
                {"Totals":9,"Value":"c","variable":"alpha","value":3,"cumsum":3},
                {"Totals":9,"Value":"D","variable":"alpha","value":3,"cumsum":3},
                {"Totals":9,"Value":"E","variable":"alpha","value":4,"cumsum":4},
                {"Totals":7,"Value":"A","variable":"beta","value":2,"cumsum":4},
                {"Totals":8,"Value":"B","variable":"beta","value":3,"cumsum":5},
                {"Totals":9,"Value":"c","variable":"beta","value":3,"cumsum":6},
                {"Totals":9,"Value":"D","variable":"beta","value":4,"cumsum":7},
                {"Totals":9,"Value":"E","variable":"beta","value":3,"cumsum":7},
                {"Totals":7,"Value":"A","variable":"gamma","value":3,"cumsum":7},
                {"Totals":8,"Value":"B","variable":"gamma","value":3,"cumsum":8},
                {"Totals":9,"Value":"c","variable":"gamma","value":3,"cumsum":9},
                {"Totals":9,"Value":"D","variable":"gamma","value":2,"cumsum":9},
                {"Totals":9,"Value":"E","variable":"gamma","value":2,"cumsum":9}]

class TestChart(unittest.TestCase):

    def test_gen_chart(self):

        chart = LineChart(
            encodings=[ Encoding("x", "Value", "nominal"),
                        Encoding("y", "Totals", "quantitative") ])

        print()
        print(VisDesign(chart=chart, data=example_data).to_vl_json())
        print()

    def test_stacked(self):

        chart = StackedChart(
            chart_ty="area",
            stack_channel="y",
            stack_ty="normalize",
            encodings=[ Encoding("x", "Value", "nominal"),
                        Encoding("y", "value", "quantitative"),
                        Encoding("color", "variable", "nominal") ])
        print()
        print(VisDesign(chart=chart, data=example_data).to_vl_json())
        print()

    def test_scatter(self):

        chart = ScatterPlot(
            mark_ty="point",
            encodings=[ Encoding("x", "Value", "nominal"),
                        Encoding("size", "value", "quantitative"),
                        Encoding("y", "variable", "nominal") ])
        print()
        print(VisDesign(chart=chart, data=example_data).to_vl_json())
        print()

    def test_layered_scatter(self):

        line_chart = LineChart(
            encodings=[ Encoding("y", "Totals", "quantitative") ])

        area_chart = StackedChart(
            chart_ty="area",
            stack_channel="y",
            stack_ty="normalize",
            encodings=[ Encoding("y", "value", "quantitative"),
                        Encoding("color", "variable", "nominal") ])

        chart = LayeredChart(
            shared_encodings=[Encoding("x", "Value", "nominal")],
            layers=[line_chart, area_chart],
            resolve={"scale": {"y": "independent"}})

        print()
        print(VisDesign(chart=chart, data=example_data).to_vl_json())
        print()


if __name__ == '__main__':
    unittest.main()