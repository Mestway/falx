import sys
import os

from flask import Flask, escape, request
import flask
import json
from flask_cors import CORS

import copy
import pandas as pd

sys.path.append(os.path.abspath('../falx'))

from falx.interface import FalxInterface

def infer_dtype(values):
    return pd.api.types.infer_dtype(values, skipna=True)

def try_infer_string_type(values):
    """try to infer datatype from values """
    dtype = pd.api.types.infer_dtype(values, skipna=False)
    ty_func = lambda l: pd.to_numeric(l)

    try:
        values = ty_func(values)
        dtype = pd.api.types.infer_dtype(values, skipna=False)
    except:
        pass

    return dtype, values

app = Flask(__name__, static_url_path='')
CORS(app)

GRAMMAR = {
    "operators": ["select", "unite", "filter", "separate", "spread", 
        "gather", "gather_neg", "group_sum", "cumsum", "mutate", "mutate_custom"],
    "filer_op": [">", "<", "=="],
    "constants": [],
    "aggr_func": ["mean", "sum", "count"],
    "mutate_op": ["+", "-"],
    "gather_max_val_list_size": 3,
    "gather_neg_max_key_list_size": 3
}

@app.route('/')
def hello():
    name = request.args.get("name", "World")

    input_data = [
        { "Bucket": "Bucket E", "Budgeted": 100, "Actual": 115 },
        { "Bucket": "Bucket D", "Budgeted": 100, "Actual": 90 },
        { "Bucket": "Bucket C", "Budgeted": 125, "Actual": 115 },
        { "Bucket": "Bucket B", "Budgeted": 125, "Actual": 140 },
        { "Bucket": "Bucket A", "Budgeted": 140, "Actual": 150 }
    ]

    raw_trace = [
        {"type": "bar", "props": { "x": "Actual", "y": 115,  "color": "Actual", "x2": "", "y2": "", "column": "Bucket E"}},
        {"type": "bar", "props": { "x": "Actual", "y": 90,"color": "Actual", "x2": "", "y2": "", "column": "Bucket D"}},
        {"type": "bar", "props": { "x": "Budgeted","y": 100,  "color": "Budgeted", "x2": "", "y2": "", "column": "Bucket D"}},
    ]

    result = FalxInterface.synthesize(
                inputs=[input_data], 
                raw_trace=raw_trace, 
                extra_consts=[],
                config={
                    "solution_limit": 10,
                    "time_limit_sec": 10,
                    "backend": "vegalite",
                    "max_prog_size": 2,
                    "grammar": GRAMMAR
                })

    for c in result:
        print(c[0])
        print(c[1].to_vl_json())

    return 'Hello!'

@app.route('/falx', methods=['GET', 'POST'])
def run_falx_synthesizer():
    if request.is_json:
        app.logger.info("# request data: ")
        content = request.get_json()
        
        input_data = content["data"]
        visual_elements = content["tags"]

        app.logger.info(input_data)
        app.logger.info(visual_elements)

        all_input_values = list(set([val for r in input_data for key, val in r.items()])) + list(set([key for key in input_data[0]]))

        post_processed_visual_elements = []
        partition_keys = set([r['type'] for r in visual_elements])
        for key in partition_keys:
            partition = [r for r in visual_elements if r['type'] == key]
            copyed_partition = copy.deepcopy(partition)

            columns = [c for c in partition[0]["props"]]
            for c in columns:
                values = [r["props"][c] for r in copyed_partition]
                if all([v == "" for v in values]):
                    continue

                ty, values = try_infer_string_type(values)

                if ty != "string":
                    for i in range(len(values)):
                        # update the value in partion by reference, force to modify into integer
                        partition[i]["props"][c] = float(values[i])

        result = FalxInterface.synthesize(
                    inputs=[input_data], 
                    raw_trace=visual_elements, 
                    extra_consts=[],
                    group_results=True,
                    config={
                        "solution_limit": 10,
                        "time_limit_sec": 10,
                        "backend": "vegalite",
                        "max_prog_size": 2,
                        "grammar": GRAMMAR
                    })

        response = flask.jsonify([{"rscript": str(result[key][0][0]), 
                                   "vl_spec": result[key][0][1].to_vl_json()} for key in result])
    else:
        response = falx.jsonify([])

    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)