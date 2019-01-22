from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import argparse
import json
import jsonschema
import os
from pprint import pprint
import subprocess

import design_enumerator
import utils


# default directories
PROJ_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
RESOURCE_DIR = os.path.join(PROJ_DIR, "resource")
TEMP_DIR = os.path.join(PROJ_DIR, "__temp__")
if not os.path.exists(TEMP_DIR): os.mkdir(TEMP_DIR)

# arguments
parser = argparse.ArgumentParser()
parser.add_argument("--input_file", dest="input_file", default=None, 
					help="input Vega-Lite spec file")
parser.add_argument("--input_dir", dest="input_dir",
					default=os.path.join(PROJ_DIR, "vl_examples"),
					help="input files; ignored if input-file is specified")
parser.add_argument("--output_dir", dest="output_dir", 
					default=TEMP_DIR, help="output directory")
parser.add_argument("--external_validation", dest="external_validation",
					default=False, help="whether enable using JS module to validate specs")

def absolute_path(p):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), p)

def external_validation(spec):
    proc = subprocess.Popen(
        args=["node", absolute_path("../js/index.js")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = proc.communicate(json.dumps(spec).encode("utf8"))

    if stderr:
        return stderr.decode("utf-8").strip()

    return stdout.decode("utf-8").strip()

def run(flags):
	"""Synthesize vega-lite schema """

	with open(os.path.join(RESOURCE_DIR, "vega-lite-schema.json")) as f:
		vl_schema = json.load(f)

	input_files = []
	if flags.input_file is not None:
		input_files.append(flags.input_file)
	else:
		for fname in os.listdir(flags.input_dir):
			if fname.endswith(".vl.json"):
				input_files.append(os.path.join(flags.input_dir, fname))

	vl_specs = [utils.load_vl_spec(f) for f in input_files]
	data_urls = [spec["data"]["url"] for spec in vl_specs if "url" in spec["data"]]

	print("# start enumeration")
	output_index = 0
	for vl_spec in vl_specs:
		if "layer" in vl_spec or "transform" in vl_spec:
			continue
		if len(vl_spec["encoding"]) != 2:
			continue 

		new_data = {"url": "data/unemployment-across-industries.json"}
		target_fields = ["series", "count"]

		candidates = design_enumerator.explore_designs(vl_spec, new_data, target_fields)
		
		for s in candidates:
			if external_validation:
				status = json.loads(external_validation(s))
				if status:
					print("-", end="", flush=True)
			try:
				jsonschema.validate(s, vl_schema)
				print(".", end="", flush=True)
			except:
				print("x", end="", flush=True)
				continue

			with open(os.path.join(flags.output_dir, "temp_{}.vl.json".format(output_index)), "w") as g:
				g.write(json.dumps(s))
			output_index += 1
	
	print("")
	print("# finish enumeration")

if __name__ == '__main__':
	flags = parser.parse_args()
	run(flags)
