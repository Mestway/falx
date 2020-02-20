import eval_utils
import json

from falx.eval_interface import FalxEvalInterface
from  falx.utils import table_utils
from timeit import default_timer as timer
import numpy as np

from pprint import pprint

from falx.visualization.chart import VisDesign, StackedBarChart, LayeredChart
from falx.visualization.matplotlib_chart import MatplotlibChart
import falx.visualization.visual_trace as visual_trace

np.random.seed(2019)

def get_mark_type(chart):
    chart_obj = chart.to_vl_obj()
    marks = [chart_obj['mark']] if "mark" in chart_obj else [layer["mark"] for layer in chart_obj["layer"]]
    marks = [m if isinstance(m, (str,)) else m["type"] for m in marks]
    return marks

def process_data(bid, num_samples_dict):

    f_in = f"../../benchmarks/{bid}.json"

    for k in [2, 3, 4]:
        if bid in num_samples_dict[k]:
            break

    num_samples = k

    with open(f_in, "r") as f:
        data = json.load(f)
        #print(data)

        input_data = data["input_data"]
        extra_consts = data["constants"] if "constants" in data else []
        vis = VisDesign.load_from_vegalite(data["vl_spec"], data["output_data"])
        full_trace = vis.eval()

        partitioned = visual_trace.partition_trace(full_trace)
 
        sample_trace = []
        raw_sample_trace = []
        raw_full_trace = []

        for key in partitioned:
            ty = "bar" if key in ["BarV","BarH"] else ("line" if key == "Line" else ("point" if key == "Point" else "area"))
            traces = partitioned[key]
            num_samples = int(np.ceil(num_samples / 2.0)) if ty == "line" or ty == "area" else num_samples
            indexes = np.random.choice(list(range(len(traces))), num_samples)
            samples = [traces[i] for i in indexes]
            
            tr_table = visual_trace.trace_to_table(samples)
            full_tr_table = visual_trace.trace_to_table(traces)

            for tr in full_tr_table[key]:
                raw_full_trace.append({"type": ty, "props": tr})

            for tr in tr_table[key]:
                raw_sample_trace.append({"type": ty, "props": tr})
                if ty == "line":
                    kreplace = lambda x: "x" if x in ["x1", "x2"] else "y" if x in ["y1", "y2"] else x
                    sample_trace.append({"type": ty, "props": {kreplace(k):tr[k] for k in ["x1", "y1", "size", "color", "column"] if k in tr}})
                    sample_trace.append({"type": ty, "props": {kreplace(k):tr[k] for k in ["x2", "y2", "size", "color", "column"] if k in tr}})
                elif ty == "bar":
                    kreplace = lambda x: "x" if x in ["x1"] else "y" if x in ["y1"] else x
                    sample_trace.append({"type": ty, "props": {kreplace(k):tr[k] for k in tr}})
                elif ty == "point":
                    sample_trace.append({"type": ty, "props": tr})
                elif ty == "area":
                    kreplace = lambda x: "x" if x in ["x1", "x2"] else ("y2" if x in ["yb1", "yb2"] else "y" if x in ["yt1", "yt2"] else x)
                    sample_trace.append({"type": ty, "props": {kreplace(k):tr[k] for k in ["x1", "yt1", "yb1", "color", "column"] if k in tr}})
                    sample_trace.append({"type": ty, "props": {kreplace(k):tr[k] for k in ["x2", "yt2", "yb2", "color", "column"] if k in tr}})

        #pprint(sample_trace)

        # abstract_designs = VisDesign.inv_eval(full_trace)
        # abstract_designs.sort(key=lambda x: len(x[0].values[0]) if not isinstance(x[0], (list,)) else sum([len(y.values[0]) for y in x[0]]))

        # sample_outputs = []

        # for full_sym_data, chart in abstract_designs:

        #     if (isinstance(chart, (StackedBarChart, )) 
        #         or (isinstance(chart, (LayeredChart, )) and 
        #             any([isinstance(x, (StackedBarChart,)) for x in chart.layers]))):
        #         continue

        #     marks = get_mark_type(chart)

        #     if not isinstance(full_sym_data, (list,)):
        #         sample_output = eval_utils.sample_symbolic_table(full_sym_data, num_samples)
        #         sample_outputs.append((marks[0], sample_output))
        #     else:
        #         # multi-layer charts
        #         for i, full_output in enumerate(full_sym_data):
        #             sample_table = eval_utils.sample_symbolic_table(full_output, num_samples)
        #             sample_outputs.append((marks[i], sample_table))
        #     break

        # sample_trace = []
        # for t in sample_outputs:
        #     mark = t[0]
        #     for row in t[1].values:
        #         sample_trace.append({"type": mark, "props": {key.replace("c_", ""): row[key] for key in row}})

        data["sample_trace"] = sample_trace
        data["raw_sample_trace"] = raw_sample_trace
        data["raw_full_trace"] = raw_full_trace

    return data


if __name__ == '__main__':
    benchmark_ids = [
      "test_1", "test_2", "test_3", "test_4", "test_5", "test_6", "test_7",
      "test_8", "test_9", "test_10", "test_11", "test_12", "test_13", "test_14",
      "test_15", "test_16", "test_17", "test_18", "test_19", "test_20", "test_21", 
      "test_22", "test_23",
      "001", "002", "003", "004", "005", "006", "007", "008", "009", "010",
      "011", "012", "013", "014", "015", "016", "017", "018", "019", "020",
      "021", "022", "023", "024", "025", "026", "027", "028", "029", "030",
      "031", "032", "033", "034", "035", "036", "037", "038", "039", "040",
      "041", "042", "043", "044", "045", "046", "047", "048", "049", "050",
      "051", "052", "053", "054", "055", "056", "057", "058", "059", "060",
      ]

    num_samples_dict = {
        1: ['test_21', '050', '025', '058', '001', '011', 'test_7', '042', '032', '012', 'test_15', 'test_10', '023', 'test_1', '052', 'test_6', '035', '010', '006', '054', '051', 'test_14', '056', '024', '017', '053', '020', '033', '031', 'test_8', '047', '030', '029', 'test_2', 'test_11', 'test_13'],
        2: ['test_21', '025', '050', '001', '011', '058', '012', '032', 'test_7', 'test_10', '010', '017', '023', '042', '052', 'test_15', '035', 'test_6', 'test_1', '006', '054', '051', 'test_14', '024', '053', '056', '009', '020', '033', 'test_8', '031', '047', '030', 'test_16', '029', 'test_2', '034', 'test_13', '014', '037', 'test_12', 'test_11', 'test_23'],
        3: ['test_21', '015', '050', '001', '025', '011', '058', '012', '006', '032', 'test_7', '010', 'test_10', '017', '023', 'test_1', '042', 'test_6', 'test_15', '052', '035', '005', '045', '054', '051', 'test_14', '007', '038', '041', '022', '024', '053', '056', '020', '009', '033', 'test_22', '004', 'test_8', 'test_2', '031', 'test_13', '047', 'test_16', '029', '030', '034', '014', '037', 'test_12', 'test_11', 'test_23', '044'],
        4: ['058', '015', 'test_21', '050', '006', '011', '032', 'test_7', '010', 'test_10', '012', '017', '025', 'test_14', '023', '042', 'test_15', 'test_1', '052', 'test_6', '005', '035', '045', '001', '051', '038', '007', '041', '022', '054', '016', '024', '056', '053', '009', '020', 'test_17', '033', '021', '008', '044', '031', '030', '047', 'test_16', 'test_22', '004', '029', 'test_13', '034', 'test_2', 'test_8', '014', 'test_11', 'test_12', '037', 'test_23']
    }

    #benchmark_ids = ["test_4"]

    full_data = []
    for i, bid in enumerate(benchmark_ids):
        data = process_data(bid, num_samples_dict)
        full_data.append(data)
    print(json.dumps(full_data))
