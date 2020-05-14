import sys
import os

from flask import Flask, escape, request, send_from_directory, redirect, url_for

import flask
import json
from flask_cors import CORS

import copy
import pandas as pd
import time

sys.path.append(os.path.abspath('../falx'))

from falx.interface import FalxInterface
from falx.utils import vis_utils

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
        "gather", "group_sum", "cumsum", "mutate", "mutate_custom"],
    "filer_op": [">", "<", "=="],
    "constants": [],
    "aggr_func": ["mean", "sum", "count"],
    "mutate_op": ["+", "-"],
    "gather_max_val_list_size": 3,
    "gather_max_key_list_size": 3
}

@app.route('/static/media/<path:filename>')
def download_file(filename):
    return send_from_directory(app.static_folder + "/media", filename)

@app.route('/hello')
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

@app.route("/", defaults={"path": ""})
def index_alt(path):
    return send_from_directory(app.static_folder, "index.html")

@app.errorhandler(404)
def page_not_found(e):
    # your processing here
    return send_from_directory(app.static_folder, "index.html")

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
        splitted_values = []
        for v in all_input_values:
            if isinstance(v, (str,)) and "_" in v:
                splitted_values += v.split("_")
            if isinstance(v, (str,)) and "-" in v:
                splitted_values += v.split("-")
        all_input_values += splitted_values
        all_input_values = set(all_input_values)

        print(all_input_values)

        post_processed_visual_elements = []
        partition_keys = set([r['type'] for r in visual_elements])
        for key in partition_keys:

            partition = [r for r in visual_elements if r['type'] == key]
            copyed_partition = copy.deepcopy(partition)

            columns = [c for c in partition[0]["props"]]
            all_empty_columns = [c for c in columns if all([r["props"][c] == "" for r in copyed_partition])]

            for c in columns:
                # for x, y, we also need to look into columns from x1, x2 etc, not just x, y themselves
                if c.startswith("x"):
                    related_columns = ["x", "x1", "x2", "x_left", "x_right"]
                elif c.startswith("y"):
                    related_columns = ["y", "y1", "y2", "y_top_left", "y_bot_left", "y_top_right", "y_bot_right"]
                else:
                    related_columns = [c]

                related_columns = [c for c in related_columns if c in columns and c not in all_empty_columns]

                values = [r["props"][x] for r in copyed_partition for x in related_columns]
                if all([v == "" for v in values]):
                    continue

                if infer_dtype(values) != "string":
                    continue

                # don't try to force conversion if it is not 
                if len([x for x in values if x not in all_input_values]) == 0:
                    continue

                ty, values = try_infer_string_type(values)

                if ty != "string":
                    # locate values in the column c and update their types by reference
                    values_in_c = [r["props"][c] for r in copyed_partition]
                    _, values_in_c = try_infer_string_type(values_in_c)
                    for i in range(len(values_in_c)):
                        # update the value in partion by reference, force to modify into integer
                        partition[i]["props"][c] = float(values_in_c[i])

        start_time = time.time()

        time_limit_sec = 15
        result = FalxInterface.synthesize(
                    inputs=[input_data], 
                    raw_trace=visual_elements, 
                    extra_consts=[],
                    group_results=True,
                    config={
                        "solution_limit": 10,
                        "time_limit_sec": time_limit_sec,
                        "backend": "vegalite",
                        "max_prog_size": 2,
                        "grammar": GRAMMAR
                    })
        time_spent = time.time() - start_time

        print("==> time spent: {}".format(time_spent))

        # perform repairs on synthesized visdualization
        final_results = {}
        for key in result:
            for p in result[key]:
                spec_w_data = p[1].to_vl_obj()
                data = spec_w_data["data"]["values"]
                spec = spec_w_data
                spec = vis_utils.post_process_spec(spec, data)
                if spec is not None:
                    spec["data"] = {"values": data}
                    if key not in final_results:
                        final_results[key] = []
                    final_results[key].append((p[0], spec))

        
        response = flask.jsonify({
            "status": "timeout" if time_spent >= time_limit_sec else "ok",
            "time_spent": time_spent,
            "result": [{"rscript": str(final_results[key][0][0]), 
                        "vl_spec": json.dumps(final_results[key][0][1])} for key in final_results]
        })
    else:
        response = flask.jsonify({
            "time_spent": "",
            "status": "error",
            "result": []
        })

    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

if __name__ == '__main__':
    #app.run(debug=True, host='127.0.0.1', port=5000)
    app.run(host='0.0.0.0', port=5000, threaded=True)