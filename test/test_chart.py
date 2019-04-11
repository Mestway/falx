import unittest
from falx.chart import *

test_data = [{"Totals":7,"Value":"A","variable":"alpha","value":2,"cumsum":2},
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
                        Encoding("y", "Totals", "quantitative"),
                        Encoding("color", "variable", "nominal")])
        design = VisDesign(chart=chart, data=test_data)
        

    def test_stacked(self):
        chart = StackedChart(
            chart_ty="bar",
            orientation="vertical",
            encodings=[ Encoding("x", "Value", "nominal"),
                        Encoding("y", "value", "quantitative"),
                        Encoding("color", "variable", "nominal") ])
        #print(VisDesign(chart=chart, data=test_data).to_vl_json())
        design = VisDesign(chart=chart, data=test_data)
        print(design.to_vl_json())
        pprint(design.eval())

    def test_scatter(self):
        chart = ScatterPlot(
            mark_ty="point",
            encodings=[ Encoding("x", "Value", "nominal"),
                        Encoding("size", "value", "quantitative"),
                        Encoding("y", "variable", "nominal") ])
        #print(VisDesign(chart=chart, data=test_data).to_vl_json())

    def test_layered_scatter(self):
        line_chart = ScatterPlot(
            mark_ty="point",
            encodings=[ Encoding("y", "Totals", "quantitative") ])

        area_chart = StackedChart(
            chart_ty="bar",
            orientation="vertical",
            encodings=[ Encoding("y", "value", "quantitative"),
                        Encoding("color", "variable", "nominal") ])

        chart = LayeredChart(
            shared_encodings=[Encoding("x", "Value", "nominal")],
            layers=[line_chart, area_chart],
            resolve={"scale": {"y": "independent"}})

        design = VisDesign(chart=chart, data=test_data)
        #print(design.to_vl_json())
        #pprint(design.eval())

    def test_grouped_bar(self):
        bar_chart = BarChart(
            encodings=[ Encoding("x", "Value", "nominal"),
                        Encoding("y", "value", "quantitative") ],
            orientation="vertical")

        chart = GroupChart(
            enc_group=Encoding("group", "variable", "nominal"),
            layer=bar_chart)

        design = VisDesign(chart=chart, data=test_data)
        #print(design.to_vl_json())
        #pprint(design.eval())


if __name__ == '__main__':
    unittest.main()