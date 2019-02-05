from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import argparse
import json
import jsonschema
import os
from pprint import pprint

import design_enumerator
import utils

from morpheus_enumerator import *

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

parser.add_argument("--validation", dest="validation", default=0, type=int,
					help="whether to run external validation for VegaLite spec,"
						 "Mode: 0 -- no extra validation"
						 "      1 -- schema check"
						 "      2 -- schema check and compilation check")


def get_sample_data():

	##### Input-output constraint
	benchmark1_input = robjects.r('''
    dat <- read.table(header = TRUE, text = 
        "gene                   value_1                     value_2
        XLOC_000060           3.662330                   0.3350140
        XLOC_000074           2.568130                   0.0426299")
	dat
   ''')

	benchmark1_output = robjects.r('''
	dat2 <- read.table(text="
	nam val_round1 val_round2 var1_round1 var1_round2 var2_round1 var2_round2
	bar  0.1241058 0.03258235          22          11          33          44
	foo  0.1691220 0.18570826          22          11          33          44
	", header=T)
	dat2
   ''')

	# logger.info('Parsing Spec...')
	spec = None
	morpheus_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "dsl", "morpheus.tyrell")
	with open(morpheus_path, 'r') as f:
		m_spec_str = f.read()
		spec = S.parse(m_spec_str)

	synthesizer = Synthesizer(
		#loc: # of function productions
		enumerator=SmtEnumerator(spec, depth=2, loc=1),
		# enumerator=SmtEnumerator(spec, depth=3, loc=2),
		# enumerator=SmtEnumerator(spec, depth=4, loc=3),
		decider=ExampleConstraintDecider(
			spec=spec,
			interpreter=MorpheusInterpreter(),
			examples=[
				Example(input=['dat'], output='dat2'),
			],
			equal_output=eq_r
		)
	)

	prog = synthesizer.synthesize()

def run(flags):
	"""Synthesize vega-lite schema """

	with open(os.path.join(RESOURCE_DIR, "vega-lite-schema.json")) as f:
		vl_schema = json.load(f)

	input_files = []
	get_sample_data()
	global g_list

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
		for morpheus_data in g_list:
			new_data = morpheus_data

			target_fields = {
				"series": {"type": "string"},
				"count": {"type": "integer"}
			}

			candidates = design_enumerator.explore_designs(vl_spec, new_data, target_fields)
			
			for spec in candidates:
				if flags.validation != 0:
					external_validation = True if flags.validation == 2 else False
					status, message = design_enumerator.validate_spec(spec, vl_schema, external_validation)
					if not status:
						print("x", end="", flush=True)
				print(".", end="", flush=True)
				with open(os.path.join(flags.output_dir, "temp_{}.vl.json".format(output_index)), "w") as g:
					g.write(json.dumps(spec))
				output_index += 1

	print("")
	print("# finish enumeration {}".format(output_index))

if __name__ == '__main__':
	flags = parser.parse_args()
	run(flags)
