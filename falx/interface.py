import json
import itertools
from pprint import pprint
import numpy as np
import copy

from falx.table import synthesizer as table_synthesizer

from falx.utils import synth_utils
from falx.utils import eval_utils
from falx.utils import vis_utils

from falx.visualization.chart import VisDesign
from falx.visualization.matplotlib_chart import MatplotlibChart
from falx.visualization import visual_trace

from falx.logger import get_logger

from pprint import pprint

np.random.seed(2019)

logger = get_logger("interface")
logger.setLevel('INFO')

class FalxInterface(object):

    # the default confifguration for the synthesizer
    default_config = {
        # configurations related to table transformation program synthesizer
        "solution_limit": 5,
        "time_limit_sec": 10,
        "max_prog_size": 2,

        "grammar": {
            "operators": ["select", "unite", "filter", "separate", "spread", 
                "gather", "gather_neg", "group_sum", "cumsum", "mutate", "mutate_custom"],
            "filer_op": [">", "<", "=="],
            "constants": [],
            "aggr_func": ["mean", "sum", "count"],
            "mutate_op": ["+", "-"],
            "gather_max_val_list_size": 3,
            "gather_max_key_list_size": 3,
            "consider_non_consecutive_gather_keys": False
        },

        "disable_provenance_analysis": False,

        # set the visualization backend, one of "vegalite, ggplot2, matplotlib"
        # ggplot2 and matplotlib have some feature restrictions
        "vis_backend": "vegalite"
    }

    def group_results(results):
        """Given a list of candidate program, evaluate them and group them into equivalence classes."""
        equiv_classes = {}
        for tbl_prog, vis_spec in results:
            full_trace = vis_spec.eval()
            fronzen_trace = json.dumps(visual_trace.trace_to_table(full_trace), sort_keys=True)
            if fronzen_trace not in equiv_classes:
                equiv_classes[fronzen_trace] = []
            equiv_classes[fronzen_trace].append((tbl_prog, vis_spec))
        return equiv_classes

    def update_config(user_config):
        config = copy.copy(FalxInterface.default_config)
        for key in user_config:
            if key in config:
                if key == "grammar":
                    for k2 in user_config["grammar"]:
                        if k2 in config["grammar"]:
                            config["grammar"][k2] = user_config["grammar"][k2]
                else:
                    config[key] = user_config[key]
            else:
                logger.warning("[] Key {} is not part of the synthesizer config.".format(key))

        assert config["vis_backend"] in ["vegalite", "matplotlib"]
        assert config["solution_limit"] >= 1
        assert config["time_limit_sec"] > 0
        assert config["max_prog_size"] >= 0

        return config

    @staticmethod
    def synthesize(inputs, raw_trace, extra_consts=[], group_results=False, config={}):
        """synthesize table prog and vis prog from input and output traces
        Inputs:
            input tables: a list of input tables that the synthesizer will take into consideration
            raw_trace: visualization elements in the following format
                vtrace = [
                  {"type": "line", "props": {"x1": "Y1", "y1": 0.52, "x2": "Y2", "y2": 0.57, "color": "", "column": ""}},
                  {"type": "line", "props": {"x1": "Y2", "y1": 0.57, "x2": "Y3", "y2": 0.6, "color": "", "column": ""}}
                ]
            extra_consts: extra constant that the synthesizer will take into consideration
            group_results: whether the output is grouped based on equivalence classes 
                            (i.e., the programs generate same visualizations)
            config: configurations sent to the synthesizer contains the following options
                    { "solution_limit": ..., "time_limit_sec": ...,
                      "starting_search_program_length": 1, "stop_search_program_length": 2,
                      "grammar_base_file": "dsl/tidyverse.tyrell.base",
                      "block_sketches": [], "block_program_symbols": [], "vis_backend": "vegalite" }
        """

        # update synthesizer config

        config = FalxInterface.update_config(config)

        example_trace = visual_trace.load_trace(raw_trace)

        # apply inverse semantics to obtain symbolic output table and vis programs
        abstract_designs = None
        if config["vis_backend"] == "vegalite":
            abstract_designs = VisDesign.inv_eval(example_trace)  
        else:
            abstract_designs = MatplotlibChart.inv_eval(example_trace)
        
        # sort pairs based on complexity of tables
        abstract_designs.sort(key=lambda x: len(x[0].values[0]) 
                                if not isinstance(x[0], (list,)) else sum([len(y.values[0]) for y in x[0]]))

        logger.info("# Synthesizer configuration")
        logger.info(json.dumps(config, indent=2))

        candidates = []
        for sym_data, chart in abstract_designs:

            # split case based on single layered chart or multi layered chart
            if not isinstance(sym_data, (list,)):
                # single-layer chart

                synthesizer = table_synthesizer.Synthesizer(config=config["grammar"])

                print("==> table synthesis input:")
                print(sym_data.instantiate())

                candidate_progs = synthesizer.enumerative_synthesis(
                                    inputs, sym_data.instantiate(), 
                                    max_prog_size=config["max_prog_size"],
                                    time_limit_sec=config["time_limit_sec"],
                                    solution_limit=config["solution_limit"],
                                    disable_provenance_analysis=config["disable_provenance_analysis"])

                for p in candidate_progs:
                    output = p.eval(inputs).to_dict(orient="records")

                    field_mappings = synth_utils.align_table_schema(sym_data.values, output, find_all_alignments=True)
                    assert(len(field_mappings) > 0)

                    for field_mapping in field_mappings:
                        if config["vis_backend"] == "vegalite":
                            vis_design = VisDesign(data=output, chart=copy.deepcopy(chart))
                            vis_design.update_field_names(field_mapping)
                            candidates.append((p.stmt_string(), vis_design))
                        else:
                            vis_design = MatplotlibChart(output, copy.deepcopy(chart))
                            candidates.append((p.stmt_string(), vis_design.to_string_spec(field_mapping)))
            else:
                synthesizer = table_synthesizer.Synthesizer(config=config["grammar"])

                
                # multi-layer charts
                # layer_candidate_progs[i] contains all programs that transform inputs to output[i]
                # synthesize table transformation programs for each layer
                layer_candidate_progs = []
                for d in sym_data:
                    print("==> table synthesis input:")
                    print(d.instantiate())
                    layer_candidate_progs.append(
                        synthesizer.enumerative_synthesis(
                            inputs, d.instantiate(), 
                            max_prog_size=config["max_prog_size"], 
                            time_limit_sec=config["time_limit_sec"],
                            solution_limit=config["solution_limit"]))
            
                # iterating over combinations for different layers
                layer_id_lists = [list(range(len(l))) for l in layer_candidate_progs]
                for layer_id_choices in itertools.product(*layer_id_lists):

                    #layer_prog[i] is the transformation program for the i-th layer
                    progs = [layer_candidate_progs[i][layer_id_choices[i]] for i in range(len(layer_id_choices))]

                    # apply each program on inputs to get output table for each layer
                    outputs = [p.eval(inputs).to_dict(orient="records") for p in progs]

                    all_field_mappings = [synth_utils.align_table_schema(sym_data[k].values, output, find_all_alignments=True) 
                            for k, output in enumerate(outputs)]

                    mapping_id_lists = [list(range(len(l))) for l in all_field_mappings]
                    for mapping_id_choices in itertools.product(*mapping_id_lists):

                        field_mappings = [all_field_mappings[i][idx] for i, idx in enumerate(mapping_id_choices)]
                        #print(field_mappings)

                        if config["vis_backend"] == "vegalite":
                            vis_design = VisDesign(data=outputs, chart=copy.deepcopy(chart))
                            vis_design.update_field_names(field_mappings)
                            candidates.append(([p.stmt_string() for p in progs], vis_design))
                        else:
                            vis_design = MatplotlibChart(outputs,copy.deepcopy(chart))
                            candidates.append(([p.stmt_string() for p in progs], vis_design.to_string_spec(field_mappings)))

            #if len(candidates) > 0: break

        if group_results:
            return FalxInterface.group_results(candidates)

        return candidates

if __name__ == '__main__':

    # input_data = [
    #   { "Bucket": "Bucket E", "Budgeted": 100, "Actual": 115 },
    #   { "Bucket": "Bucket D", "Budgeted": 100, "Actual": 90 },
    #   { "Bucket": "Bucket C", "Budgeted": 125, "Actual": 115 },
    #   { "Bucket": "Bucket B", "Budgeted": 125, "Actual": 140 },
    #   { "Bucket": "Bucket A", "Budgeted": 140, "Actual": 150 }
    # ]

    # raw_trace = [
    #   {"type": "bar", "props": { "x": "Bucket E", "y": 100,  "color": 15, "x2": "", "y2": 115, "column": ""}}
    # ]

    # result = FalxInterface.synthesize(inputs=[input_data], raw_trace=raw_trace, extra_consts=[], group_results=True)

    # for val in result:
    #     print("#####")
    #     print(val)
    #     for p in result[val]:
    #         print(p[0])
    #         #print(p[1].to_vl_json())

    # input_data = [
    #   { "Quarter": "Quarter1", "Number of Units": 23, "Actual Profits": 3358 },
    #   { "Quarter": "Quarter2", "Number of Units": 27, "Actual Profits": 3829 },
    #   { "Quarter": "Quarter3", "Number of Units": 15, "Actual Profits": 2374 },
    #   { "Quarter": "Quarter4", "Number of Units": 43, "Actual Profits": 3373 }
    # ]

    # raw_trace = [
    #   {"type": "bar", "props": { "x": "Quarter1", "y": 23,  "color": "", "x2": "", "y2": "", "column": ""}},
    #   {"type": "bar", "props": { "x": "Quarter2", "y": 27,"color": "", "x2": "", "y2": "", "column": ""}},
    #   {"type": "line", "props": {"x1": "Quarter1", "y1": 3358, "x2": "Quarter2", "y2": 3829, "color": "", "column": ""}},
    # ]
  
    # result = FalxInterface.synthesize(inputs=[input_data], raw_trace=raw_trace, extra_consts=[], group_results=True)

    # for val in result:
    #     print("#####")
    #     print(val)
    #     for p in result[val]:
    #         print("--")
    #         spec_w_data = p[1].to_vl_obj()
    #         data = spec_w_data["data"]["values"]
    #         spec = spec_w_data
    #         spec = vis_utils.try_repair_visualization(spec, data)
    #         if spec is not None:
    #             spec["data"] = {"values": data}
    #             print(p[0])
    #             print(json.dumps(spec))

    input_data = [{"year":"1850","age":"0","sex":"M","people":"1483789"},{"year":"1850","age":"0","sex":"F","people":"1450376"},{"year":"1850","age":"5","sex":"M","people":"1411067"},{"year":"1850","age":"5","sex":"F","people":"1359668"},{"year":"1850","age":"10","sex":"M","people":"1260099"},{"year":"1850","age":"10","sex":"F","people":"1216114"},{"year":"1850","age":"15","sex":"M","people":"1077133"},{"year":"1850","age":"15","sex":"F","people":"1110619"},{"year":"1850","age":"20","sex":"M","people":"1017281"},{"year":"1850","age":"20","sex":"F","people":"1003841"},{"year":"1850","age":"25","sex":"M","people":"862547"},{"year":"1850","age":"25","sex":"F","people":"799482"},{"year":"1850","age":"30","sex":"M","people":"730638"},{"year":"1850","age":"30","sex":"F","people":"639636"},{"year":"1850","age":"35","sex":"M","people":"588487"},{"year":"1850","age":"35","sex":"F","people":"505012"},{"year":"1850","age":"40","sex":"M","people":"475911"},{"year":"1850","age":"40","sex":"F","people":"428185"},{"year":"1850","age":"45","sex":"M","people":"384211"},{"year":"1850","age":"45","sex":"F","people":"341254"},{"year":"1850","age":"50","sex":"M","people":"321343"},{"year":"1850","age":"50","sex":"F","people":"286580"},{"year":"1850","age":"55","sex":"M","people":"194080"},{"year":"1850","age":"55","sex":"F","people":"187208"},{"year":"1850","age":"60","sex":"M","people":"174976"},{"year":"1850","age":"60","sex":"F","people":"162236"},{"year":"1850","age":"65","sex":"M","people":"106827"},{"year":"1850","age":"65","sex":"F","people":"105534"},{"year":"1850","age":"70","sex":"M","people":"73677"},{"year":"1850","age":"70","sex":"F","people":"71762"},{"year":"1850","age":"75","sex":"M","people":"40834"},{"year":"1850","age":"75","sex":"F","people":"40229"},{"year":"1850","age":"80","sex":"M","people":"23449"},{"year":"1850","age":"80","sex":"F","people":"22949"},{"year":"1850","age":"85","sex":"M","people":"8186"},{"year":"1850","age":"85","sex":"F","people":"10511"},{"year":"1850","age":"90","sex":"M","people":"5259"},{"year":"1850","age":"90","sex":"F","people":"6569"},{"year":"1860","age":"0","sex":"M","people":"2120846"},{"year":"1860","age":"0","sex":"F","people":"2092162"},{"year":"1860","age":"5","sex":"M","people":"1804467"},{"year":"1860","age":"5","sex":"F","people":"1778772"},{"year":"1860","age":"10","sex":"M","people":"1612640"},{"year":"1860","age":"10","sex":"F","people":"1540350"},{"year":"1860","age":"15","sex":"M","people":"1438094"},{"year":"1860","age":"15","sex":"F","people":"1495999"},{"year":"1860","age":"20","sex":"M","people":"1351121"},{"year":"1860","age":"20","sex":"F","people":"1370462"},{"year":"1860","age":"25","sex":"M","people":"1217615"},{"year":"1860","age":"25","sex":"F","people":"1116373"},{"year":"1860","age":"30","sex":"M","people":"1043174"},{"year":"1860","age":"30","sex":"F","people":"936055"},{"year":"1860","age":"35","sex":"M","people":"866910"},{"year":"1860","age":"35","sex":"F","people":"737136"},{"year":"1860","age":"40","sex":"M","people":"699434"},{"year":"1860","age":"40","sex":"F","people":"616826"},{"year":"1860","age":"45","sex":"M","people":"552404"},{"year":"1860","age":"45","sex":"F","people":"461739"},{"year":"1860","age":"50","sex":"M","people":"456176"},{"year":"1860","age":"50","sex":"F","people":"407305"},{"year":"1860","age":"55","sex":"M","people":"292417"},{"year":"1860","age":"55","sex":"F","people":"267224"},{"year":"1860","age":"60","sex":"M","people":"260887"},{"year":"1860","age":"60","sex":"F","people":"249735"},{"year":"1860","age":"65","sex":"M","people":"149331"},{"year":"1860","age":"65","sex":"F","people":"141405"},{"year":"1860","age":"70","sex":"M","people":"98465"},{"year":"1860","age":"70","sex":"F","people":"101778"},{"year":"1860","age":"75","sex":"M","people":"56699"},{"year":"1860","age":"75","sex":"F","people":"57597"},{"year":"1860","age":"80","sex":"M","people":"29007"},{"year":"1860","age":"80","sex":"F","people":"29506"},{"year":"1860","age":"85","sex":"M","people":"10434"},{"year":"1860","age":"85","sex":"F","people":"14053"},{"year":"1860","age":"90","sex":"M","people":"7232"},{"year":"1860","age":"90","sex":"F","people":"6622"},{"year":"1870","age":"0","sex":"M","people":"2800083"},{"year":"1870","age":"0","sex":"F","people":"2717102"},{"year":"1870","age":"5","sex":"M","people":"2428469"},{"year":"1870","age":"5","sex":"F","people":"2393680"},{"year":"1870","age":"10","sex":"M","people":"2427341"},{"year":"1870","age":"10","sex":"F","people":"2342670"},{"year":"1870","age":"15","sex":"M","people":"1958390"},{"year":"1870","age":"15","sex":"F","people":"2077248"},{"year":"1870","age":"20","sex":"M","people":"1805303"},{"year":"1870","age":"20","sex":"F","people":"1909382"},{"year":"1870","age":"25","sex":"M","people":"1509059"},{"year":"1870","age":"25","sex":"F","people":"1574285"},{"year":"1870","age":"30","sex":"M","people":"1251534"},{"year":"1870","age":"30","sex":"F","people":"1275629"},{"year":"1870","age":"35","sex":"M","people":"1185336"},{"year":"1870","age":"35","sex":"F","people":"1137490"},{"year":"1870","age":"40","sex":"M","people":"968861"},{"year":"1870","age":"40","sex":"F","people":"944401"},{"year":"1870","age":"45","sex":"M","people":"852672"},{"year":"1870","age":"45","sex":"F","people":"747916"},{"year":"1870","age":"50","sex":"M","people":"736387"},{"year":"1870","age":"50","sex":"F","people":"637801"},{"year":"1870","age":"55","sex":"M","people":"486036"},{"year":"1870","age":"55","sex":"F","people":"407819"},{"year":"1870","age":"60","sex":"M","people":"399264"},{"year":"1870","age":"60","sex":"F","people":"374801"},{"year":"1870","age":"65","sex":"M","people":"260829"},{"year":"1870","age":"65","sex":"F","people":"239080"},{"year":"1870","age":"70","sex":"M","people":"173364"},{"year":"1870","age":"70","sex":"F","people":"165501"},{"year":"1870","age":"75","sex":"M","people":"86929"},{"year":"1870","age":"75","sex":"F","people":"89540"},{"year":"1870","age":"80","sex":"M","people":"47427"},{"year":"1870","age":"80","sex":"F","people":"54190"},{"year":"1870","age":"85","sex":"M","people":"15891"},{"year":"1870","age":"85","sex":"F","people":"19302"},{"year":"1870","age":"90","sex":"M","people":"8649"},{"year":"1870","age":"90","sex":"F","people":"13068"},{"year":"1880","age":"0","sex":"M","people":"3533662"},{"year":"1880","age":"0","sex":"F","people":"3421597"},{"year":"1880","age":"5","sex":"M","people":"3297503"},{"year":"1880","age":"5","sex":"F","people":"3179142"},{"year":"1880","age":"10","sex":"M","people":"2911924"},{"year":"1880","age":"10","sex":"F","people":"2813550"},{"year":"1880","age":"15","sex":"M","people":"2457734"},{"year":"1880","age":"15","sex":"F","people":"2527818"},{"year":"1880","age":"20","sex":"M","people":"2547780"},{"year":"1880","age":"20","sex":"F","people":"2512803"},{"year":"1880","age":"25","sex":"M","people":"2119393"},{"year":"1880","age":"25","sex":"F","people":"1974241"},{"year":"1880","age":"30","sex":"M","people":"1749107"},{"year":"1880","age":"30","sex":"F","people":"1596772"},{"year":"1880","age":"35","sex":"M","people":"1540772"},{"year":"1880","age":"35","sex":"F","people":"1483717"},{"year":"1880","age":"40","sex":"M","people":"1237347"},{"year":"1880","age":"40","sex":"F","people":"1239435"},{"year":"1880","age":"45","sex":"M","people":"1065973"},{"year":"1880","age":"45","sex":"F","people":"1003711"},{"year":"1880","age":"50","sex":"M","people":"964484"},{"year":"1880","age":"50","sex":"F","people":"863012"},{"year":"1880","age":"55","sex":"M","people":"679147"},{"year":"1880","age":"55","sex":"F","people":"594843"},{"year":"1880","age":"60","sex":"M","people":"580298"},{"year":"1880","age":"60","sex":"F","people":"526956"},{"year":"1880","age":"65","sex":"M","people":"369398"},{"year":"1880","age":"65","sex":"F","people":"346303"},{"year":"1880","age":"70","sex":"M","people":"255422"},{"year":"1880","age":"70","sex":"F","people":"251860"},{"year":"1880","age":"75","sex":"M","people":"141628"},{"year":"1880","age":"75","sex":"F","people":"143513"},{"year":"1880","age":"80","sex":"M","people":"67526"},{"year":"1880","age":"80","sex":"F","people":"77290"},{"year":"1880","age":"85","sex":"M","people":"22437"},{"year":"1880","age":"85","sex":"F","people":"31227"},{"year":"1880","age":"90","sex":"M","people":"10272"},{"year":"1880","age":"90","sex":"F","people":"15451"},{"year":"1900","age":"0","sex":"M","people":"4619544"},{"year":"1900","age":"0","sex":"F","people":"4589196"},{"year":"1900","age":"5","sex":"M","people":"4465783"},{"year":"1900","age":"5","sex":"F","people":"4390483"},{"year":"1900","age":"10","sex":"M","people":"4057669"},{"year":"1900","age":"10","sex":"F","people":"4001749"},{"year":"1900","age":"15","sex":"M","people":"3774846"},{"year":"1900","age":"15","sex":"F","people":"3801743"},{"year":"1900","age":"20","sex":"M","people":"3694038"},{"year":"1900","age":"20","sex":"F","people":"3751061"},{"year":"1900","age":"25","sex":"M","people":"3389280"},{"year":"1900","age":"25","sex":"F","people":"3236056"},{"year":"1900","age":"30","sex":"M","people":"2918964"},{"year":"1900","age":"30","sex":"F","people":"2665174"},{"year":"1900","age":"35","sex":"M","people":"2633883"},{"year":"1900","age":"35","sex":"F","people":"2347737"},{"year":"1900","age":"40","sex":"M","people":"2261070"},{"year":"1900","age":"40","sex":"F","people":"2004987"},{"year":"1900","age":"45","sex":"M","people":"1868413"},{"year":"1900","age":"45","sex":"F","people":"1648025"},{"year":"1900","age":"50","sex":"M","people":"1571038"},{"year":"1900","age":"50","sex":"F","people":"1411981"},{"year":"1900","age":"55","sex":"M","people":"1161908"},{"year":"1900","age":"55","sex":"F","people":"1064632"},{"year":"1900","age":"60","sex":"M","people":"916571"},{"year":"1900","age":"60","sex":"F","people":"887508"},{"year":"1900","age":"65","sex":"M","people":"672663"},{"year":"1900","age":"65","sex":"F","people":"640212"},{"year":"1900","age":"70","sex":"M","people":"454747"},{"year":"1900","age":"70","sex":"F","people":"440007"},{"year":"1900","age":"75","sex":"M","people":"268211"},{"year":"1900","age":"75","sex":"F","people":"265879"},{"year":"1900","age":"80","sex":"M","people":"127435"},{"year":"1900","age":"80","sex":"F","people":"132449"},{"year":"1900","age":"85","sex":"M","people":"44008"},{"year":"1900","age":"85","sex":"F","people":"48614"},{"year":"1900","age":"90","sex":"M","people":"15164"},{"year":"1900","age":"90","sex":"F","people":"20093"},{"year":"1910","age":"0","sex":"M","people":"5296823"},{"year":"1910","age":"0","sex":"F","people":"5287477"},{"year":"1910","age":"5","sex":"M","people":"4991803"},{"year":"1910","age":"5","sex":"F","people":"4866139"},{"year":"1910","age":"10","sex":"M","people":"4650747"},{"year":"1910","age":"10","sex":"F","people":"4471887"},{"year":"1910","age":"15","sex":"M","people":"4566154"},{"year":"1910","age":"15","sex":"F","people":"4592269"},{"year":"1910","age":"20","sex":"M","people":"4637632"},{"year":"1910","age":"20","sex":"F","people":"4447683"},{"year":"1910","age":"25","sex":"M","people":"4257755"},{"year":"1910","age":"25","sex":"F","people":"3946153"},{"year":"1910","age":"30","sex":"M","people":"3658125"},{"year":"1910","age":"30","sex":"F","people":"3295220"},{"year":"1910","age":"35","sex":"M","people":"3427518"},{"year":"1910","age":"35","sex":"F","people":"3088990"},{"year":"1910","age":"40","sex":"M","people":"2860229"},{"year":"1910","age":"40","sex":"F","people":"2471267"},{"year":"1910","age":"45","sex":"M","people":"2363801"},{"year":"1910","age":"45","sex":"F","people":"2114930"},{"year":"1910","age":"50","sex":"M","people":"2126516"},{"year":"1910","age":"50","sex":"F","people":"1773592"},{"year":"1910","age":"55","sex":"M","people":"1508358"},{"year":"1910","age":"55","sex":"F","people":"1317651"},{"year":"1910","age":"60","sex":"M","people":"1189421"},{"year":"1910","age":"60","sex":"F","people":"1090697"},{"year":"1910","age":"65","sex":"M","people":"850159"},{"year":"1910","age":"65","sex":"F","people":"813868"},{"year":"1910","age":"70","sex":"M","people":"557936"},{"year":"1910","age":"70","sex":"F","people":"547623"},{"year":"1910","age":"75","sex":"M","people":"322679"},{"year":"1910","age":"75","sex":"F","people":"350900"},{"year":"1910","age":"80","sex":"M","people":"161715"},{"year":"1910","age":"80","sex":"F","people":"174315"},{"year":"1910","age":"85","sex":"M","people":"59699"},{"year":"1910","age":"85","sex":"F","people":"62725"},{"year":"1910","age":"90","sex":"M","people":"23929"},{"year":"1910","age":"90","sex":"F","people":"28965"},{"year":"1920","age":"0","sex":"M","people":"5934792"},{"year":"1920","age":"0","sex":"F","people":"5694244"},{"year":"1920","age":"5","sex":"M","people":"5789008"},{"year":"1920","age":"5","sex":"F","people":"5693960"},{"year":"1920","age":"10","sex":"M","people":"5401156"},{"year":"1920","age":"10","sex":"F","people":"5293057"},{"year":"1920","age":"15","sex":"M","people":"4724365"},{"year":"1920","age":"15","sex":"F","people":"4779936"},{"year":"1920","age":"20","sex":"M","people":"4549411"},{"year":"1920","age":"20","sex":"F","people":"4742632"},{"year":"1920","age":"25","sex":"M","people":"4565066"},{"year":"1920","age":"25","sex":"F","people":"4529382"},{"year":"1920","age":"30","sex":"M","people":"4110771"},{"year":"1920","age":"30","sex":"F","people":"3982426"},{"year":"1920","age":"35","sex":"M","people":"4081543"},{"year":"1920","age":"35","sex":"F","people":"3713810"},{"year":"1920","age":"40","sex":"M","people":"3321923"},{"year":"1920","age":"40","sex":"F","people":"3059757"},{"year":"1920","age":"45","sex":"M","people":"3143891"},{"year":"1920","age":"45","sex":"F","people":"2669089"},{"year":"1920","age":"50","sex":"M","people":"2546035"},{"year":"1920","age":"50","sex":"F","people":"2200491"},{"year":"1920","age":"55","sex":"M","people":"1880975"},{"year":"1920","age":"55","sex":"F","people":"1674672"},{"year":"1920","age":"60","sex":"M","people":"1587549"},{"year":"1920","age":"60","sex":"F","people":"1382877"},{"year":"1920","age":"65","sex":"M","people":"1095956"},{"year":"1920","age":"65","sex":"F","people":"989901"},{"year":"1920","age":"70","sex":"M","people":"714618"},{"year":"1920","age":"70","sex":"F","people":"690097"},{"year":"1920","age":"75","sex":"M","people":"417292"},{"year":"1920","age":"75","sex":"F","people":"439465"},{"year":"1920","age":"80","sex":"M","people":"187000"},{"year":"1920","age":"80","sex":"F","people":"211110"},{"year":"1920","age":"85","sex":"M","people":"75991"},{"year":"1920","age":"85","sex":"F","people":"92829"},{"year":"1920","age":"90","sex":"M","people":"22398"},{"year":"1920","age":"90","sex":"F","people":"32085"},{"year":"1930","age":"0","sex":"M","people":"5875250"},{"year":"1930","age":"0","sex":"F","people":"5662530"},{"year":"1930","age":"5","sex":"M","people":"6542592"},{"year":"1930","age":"5","sex":"F","people":"6129561"},{"year":"1930","age":"10","sex":"M","people":"6064820"},{"year":"1930","age":"10","sex":"F","people":"5986529"},{"year":"1930","age":"15","sex":"M","people":"5709452"},{"year":"1930","age":"15","sex":"F","people":"5769587"},{"year":"1930","age":"20","sex":"M","people":"5305992"},{"year":"1930","age":"20","sex":"F","people":"5565382"},{"year":"1930","age":"25","sex":"M","people":"4929853"},{"year":"1930","age":"25","sex":"F","people":"5050229"},{"year":"1930","age":"30","sex":"M","people":"4424408"},{"year":"1930","age":"30","sex":"F","people":"4455213"},{"year":"1930","age":"35","sex":"M","people":"4576531"},{"year":"1930","age":"35","sex":"F","people":"4593776"},{"year":"1930","age":"40","sex":"M","people":"4075139"},{"year":"1930","age":"40","sex":"F","people":"3754022"},{"year":"1930","age":"45","sex":"M","people":"3633152"},{"year":"1930","age":"45","sex":"F","people":"3396558"},{"year":"1930","age":"50","sex":"M","people":"3128108"},{"year":"1930","age":"50","sex":"F","people":"2809191"},{"year":"1930","age":"55","sex":"M","people":"2434077"},{"year":"1930","age":"55","sex":"F","people":"2298614"},{"year":"1930","age":"60","sex":"M","people":"1927564"},{"year":"1930","age":"60","sex":"F","people":"1783515"},{"year":"1930","age":"65","sex":"M","people":"1397275"},{"year":"1930","age":"65","sex":"F","people":"1307312"},{"year":"1930","age":"70","sex":"M","people":"919045"},{"year":"1930","age":"70","sex":"F","people":"918509"},{"year":"1930","age":"75","sex":"M","people":"536375"},{"year":"1930","age":"75","sex":"F","people":"522716"},{"year":"1930","age":"80","sex":"M","people":"246708"},{"year":"1930","age":"80","sex":"F","people":"283579"},{"year":"1930","age":"85","sex":"M","people":"88978"},{"year":"1930","age":"85","sex":"F","people":"109210"},{"year":"1930","age":"90","sex":"M","people":"30338"},{"year":"1930","age":"90","sex":"F","people":"43483"},{"year":"1940","age":"0","sex":"M","people":"5294628"},{"year":"1940","age":"0","sex":"F","people":"5124653"},{"year":"1940","age":"5","sex":"M","people":"5468378"},{"year":"1940","age":"5","sex":"F","people":"5359099"},{"year":"1940","age":"10","sex":"M","people":"5960416"},{"year":"1940","age":"10","sex":"F","people":"5868532"},{"year":"1940","age":"15","sex":"M","people":"6165109"},{"year":"1940","age":"15","sex":"F","people":"6193701"},{"year":"1940","age":"20","sex":"M","people":"5682414"},{"year":"1940","age":"20","sex":"F","people":"5896002"},{"year":"1940","age":"25","sex":"M","people":"5438166"},{"year":"1940","age":"25","sex":"F","people":"5664244"},{"year":"1940","age":"30","sex":"M","people":"5040048"},{"year":"1940","age":"30","sex":"F","people":"5171522"},{"year":"1940","age":"35","sex":"M","people":"4724804"},{"year":"1940","age":"35","sex":"F","people":"4791809"},{"year":"1940","age":"40","sex":"M","people":"4437392"},{"year":"1940","age":"40","sex":"F","people":"4394061"},{"year":"1940","age":"45","sex":"M","people":"4190187"},{"year":"1940","age":"45","sex":"F","people":"4050290"},{"year":"1940","age":"50","sex":"M","people":"3785735"},{"year":"1940","age":"50","sex":"F","people":"3488396"},{"year":"1940","age":"55","sex":"M","people":"2972069"},{"year":"1940","age":"55","sex":"F","people":"2810000"},{"year":"1940","age":"60","sex":"M","people":"2370232"},{"year":"1940","age":"60","sex":"F","people":"2317790"},{"year":"1940","age":"65","sex":"M","people":"1897678"},{"year":"1940","age":"65","sex":"F","people":"1911117"},{"year":"1940","age":"70","sex":"M","people":"1280023"},{"year":"1940","age":"70","sex":"F","people":"1287711"},{"year":"1940","age":"75","sex":"M","people":"713875"},{"year":"1940","age":"75","sex":"F","people":"764915"},{"year":"1940","age":"80","sex":"M","people":"359418"},{"year":"1940","age":"80","sex":"F","people":"414761"},{"year":"1940","age":"85","sex":"M","people":"127303"},{"year":"1940","age":"85","sex":"F","people":"152131"},{"year":"1940","age":"90","sex":"M","people":"42263"},{"year":"1940","age":"90","sex":"F","people":"58119"},{"year":"1950","age":"0","sex":"M","people":"8211806"},{"year":"1950","age":"0","sex":"F","people":"7862267"},{"year":"1950","age":"5","sex":"M","people":"6706601"},{"year":"1950","age":"5","sex":"F","people":"6450863"},{"year":"1950","age":"10","sex":"M","people":"5629744"},{"year":"1950","age":"10","sex":"F","people":"5430835"},{"year":"1950","age":"15","sex":"M","people":"5264129"},{"year":"1950","age":"15","sex":"F","people":"5288742"},{"year":"1950","age":"20","sex":"M","people":"5573308"},{"year":"1950","age":"20","sex":"F","people":"5854227"},{"year":"1950","age":"25","sex":"M","people":"6007254"},{"year":"1950","age":"25","sex":"F","people":"6317332"},{"year":"1950","age":"30","sex":"M","people":"5676022"},{"year":"1950","age":"30","sex":"F","people":"5895178"},{"year":"1950","age":"35","sex":"M","people":"5511364"},{"year":"1950","age":"35","sex":"F","people":"5696261"},{"year":"1950","age":"40","sex":"M","people":"5076985"},{"year":"1950","age":"40","sex":"F","people":"5199224"},{"year":"1950","age":"45","sex":"M","people":"4533177"},{"year":"1950","age":"45","sex":"F","people":"4595842"},{"year":"1950","age":"50","sex":"M","people":"4199164"},{"year":"1950","age":"50","sex":"F","people":"4147295"},{"year":"1950","age":"55","sex":"M","people":"3667351"},{"year":"1950","age":"55","sex":"F","people":"3595158"},{"year":"1950","age":"60","sex":"M","people":"3035038"},{"year":"1950","age":"60","sex":"F","people":"3009768"},{"year":"1950","age":"65","sex":"M","people":"2421234"},{"year":"1950","age":"65","sex":"F","people":"2548250"},{"year":"1950","age":"70","sex":"M","people":"1627920"},{"year":"1950","age":"70","sex":"F","people":"1786831"},{"year":"1950","age":"75","sex":"M","people":"1006530"},{"year":"1950","age":"75","sex":"F","people":"1148469"},{"year":"1950","age":"80","sex":"M","people":"511727"},{"year":"1950","age":"80","sex":"F","people":"637717"},{"year":"1950","age":"85","sex":"M","people":"182821"},{"year":"1950","age":"85","sex":"F","people":"242798"},{"year":"1950","age":"90","sex":"M","people":"54836"},{"year":"1950","age":"90","sex":"F","people":"90766"},{"year":"1960","age":"0","sex":"M","people":"10374975"},{"year":"1960","age":"0","sex":"F","people":"10146999"},{"year":"1960","age":"5","sex":"M","people":"9495503"},{"year":"1960","age":"5","sex":"F","people":"9250741"},{"year":"1960","age":"10","sex":"M","people":"8563700"},{"year":"1960","age":"10","sex":"F","people":"8310764"},{"year":"1960","age":"15","sex":"M","people":"6620902"},{"year":"1960","age":"15","sex":"F","people":"6617493"},{"year":"1960","age":"20","sex":"M","people":"5268384"},{"year":"1960","age":"20","sex":"F","people":"5513495"},{"year":"1960","age":"25","sex":"M","people":"5311805"},{"year":"1960","age":"25","sex":"F","people":"5548259"},{"year":"1960","age":"30","sex":"M","people":"5801342"},{"year":"1960","age":"30","sex":"F","people":"6090862"},{"year":"1960","age":"35","sex":"M","people":"6063063"},{"year":"1960","age":"35","sex":"F","people":"6431337"},{"year":"1960","age":"40","sex":"M","people":"5657943"},{"year":"1960","age":"40","sex":"F","people":"5940520"},{"year":"1960","age":"45","sex":"M","people":"5345658"},{"year":"1960","age":"45","sex":"F","people":"5516028"},{"year":"1960","age":"50","sex":"M","people":"4763364"},{"year":"1960","age":"50","sex":"F","people":"4928844"},{"year":"1960","age":"55","sex":"M","people":"4170581"},{"year":"1960","age":"55","sex":"F","people":"4402878"},{"year":"1960","age":"60","sex":"M","people":"3405293"},{"year":"1960","age":"60","sex":"F","people":"3723839"},{"year":"1960","age":"65","sex":"M","people":"2859371"},{"year":"1960","age":"65","sex":"F","people":"3268699"},{"year":"1960","age":"70","sex":"M","people":"2115763"},{"year":"1960","age":"70","sex":"F","people":"2516479"},{"year":"1960","age":"75","sex":"M","people":"1308913"},{"year":"1960","age":"75","sex":"F","people":"1641371"},{"year":"1960","age":"80","sex":"M","people":"619923"},{"year":"1960","age":"80","sex":"F","people":"856952"},{"year":"1960","age":"85","sex":"M","people":"253245"},{"year":"1960","age":"85","sex":"F","people":"384572"},{"year":"1960","age":"90","sex":"M","people":"75908"},{"year":"1960","age":"90","sex":"F","people":"135774"},{"year":"1970","age":"0","sex":"M","people":"8685121"},{"year":"1970","age":"0","sex":"F","people":"8326887"},{"year":"1970","age":"5","sex":"M","people":"10411131"},{"year":"1970","age":"5","sex":"F","people":"10003293"},{"year":"1970","age":"10","sex":"M","people":"10756403"},{"year":"1970","age":"10","sex":"F","people":"10343538"},{"year":"1970","age":"15","sex":"M","people":"9605399"},{"year":"1970","age":"15","sex":"F","people":"9414284"},{"year":"1970","age":"20","sex":"M","people":"7729202"},{"year":"1970","age":"20","sex":"F","people":"8341830"},{"year":"1970","age":"25","sex":"M","people":"6539301"},{"year":"1970","age":"25","sex":"F","people":"6903041"},{"year":"1970","age":"30","sex":"M","people":"5519879"},{"year":"1970","age":"30","sex":"F","people":"5851441"},{"year":"1970","age":"35","sex":"M","people":"5396732"},{"year":"1970","age":"35","sex":"F","people":"5708021"},{"year":"1970","age":"40","sex":"M","people":"5718538"},{"year":"1970","age":"40","sex":"F","people":"6129319"},{"year":"1970","age":"45","sex":"M","people":"5794120"},{"year":"1970","age":"45","sex":"F","people":"6198742"},{"year":"1970","age":"50","sex":"M","people":"5298312"},{"year":"1970","age":"50","sex":"F","people":"5783817"},{"year":"1970","age":"55","sex":"M","people":"4762911"},{"year":"1970","age":"55","sex":"F","people":"5222164"},{"year":"1970","age":"60","sex":"M","people":"4037643"},{"year":"1970","age":"60","sex":"F","people":"4577251"},{"year":"1970","age":"65","sex":"M","people":"3142606"},{"year":"1970","age":"65","sex":"F","people":"3894827"},{"year":"1970","age":"70","sex":"M","people":"2340826"},{"year":"1970","age":"70","sex":"F","people":"3138009"},{"year":"1970","age":"75","sex":"M","people":"1599269"},{"year":"1970","age":"75","sex":"F","people":"2293376"},{"year":"1970","age":"80","sex":"M","people":"886155"},{"year":"1970","age":"80","sex":"F","people":"1417553"},{"year":"1970","age":"85","sex":"M","people":"371123"},{"year":"1970","age":"85","sex":"F","people":"658511"},{"year":"1970","age":"90","sex":"M","people":"186502"},{"year":"1970","age":"90","sex":"F","people":"314929"},{"year":"1980","age":"0","sex":"M","people":"8439366"},{"year":"1980","age":"0","sex":"F","people":"8081854"},{"year":"1980","age":"5","sex":"M","people":"8680730"},{"year":"1980","age":"5","sex":"F","people":"8275881"},{"year":"1980","age":"10","sex":"M","people":"9452338"},{"year":"1980","age":"10","sex":"F","people":"9048483"},{"year":"1980","age":"15","sex":"M","people":"10698856"},{"year":"1980","age":"15","sex":"F","people":"10410271"},{"year":"1980","age":"20","sex":"M","people":"10486776"},{"year":"1980","age":"20","sex":"F","people":"10614947"},{"year":"1980","age":"25","sex":"M","people":"9624053"},{"year":"1980","age":"25","sex":"F","people":"9827903"},{"year":"1980","age":"30","sex":"M","people":"8705835"},{"year":"1980","age":"30","sex":"F","people":"8955225"},{"year":"1980","age":"35","sex":"M","people":"6852069"},{"year":"1980","age":"35","sex":"F","people":"7134239"},{"year":"1980","age":"40","sex":"M","people":"5692148"},{"year":"1980","age":"40","sex":"F","people":"5953910"},{"year":"1980","age":"45","sex":"M","people":"5342469"},{"year":"1980","age":"45","sex":"F","people":"5697543"},{"year":"1980","age":"50","sex":"M","people":"5603709"},{"year":"1980","age":"50","sex":"F","people":"6110117"},{"year":"1980","age":"55","sex":"M","people":"5485098"},{"year":"1980","age":"55","sex":"F","people":"6160229"},{"year":"1980","age":"60","sex":"M","people":"4696140"},{"year":"1980","age":"60","sex":"F","people":"5456885"},{"year":"1980","age":"65","sex":"M","people":"3893510"},{"year":"1980","age":"65","sex":"F","people":"4896947"},{"year":"1980","age":"70","sex":"M","people":"2857774"},{"year":"1980","age":"70","sex":"F","people":"3963441"},{"year":"1980","age":"75","sex":"M","people":"1840438"},{"year":"1980","age":"75","sex":"F","people":"2951759"},{"year":"1980","age":"80","sex":"M","people":"1012886"},{"year":"1980","age":"80","sex":"F","people":"1919292"},{"year":"1980","age":"85","sex":"M","people":"472338"},{"year":"1980","age":"85","sex":"F","people":"1023115"},{"year":"1980","age":"90","sex":"M","people":"204148"},{"year":"1980","age":"90","sex":"F","people":"499046"},{"year":"1990","age":"0","sex":"M","people":"9307465"},{"year":"1990","age":"0","sex":"F","people":"8894007"},{"year":"1990","age":"5","sex":"M","people":"9274732"},{"year":"1990","age":"5","sex":"F","people":"8799955"},{"year":"1990","age":"10","sex":"M","people":"8782542"},{"year":"1990","age":"10","sex":"F","people":"8337284"},{"year":"1990","age":"15","sex":"M","people":"9020572"},{"year":"1990","age":"15","sex":"F","people":"8590991"},{"year":"1990","age":"20","sex":"M","people":"9436188"},{"year":"1990","age":"20","sex":"F","people":"9152644"},{"year":"1990","age":"25","sex":"M","people":"10658027"},{"year":"1990","age":"25","sex":"F","people":"10587292"},{"year":"1990","age":"30","sex":"M","people":"11028712"},{"year":"1990","age":"30","sex":"F","people":"11105750"},{"year":"1990","age":"35","sex":"M","people":"9853933"},{"year":"1990","age":"35","sex":"F","people":"10038644"},{"year":"1990","age":"40","sex":"M","people":"8712632"},{"year":"1990","age":"40","sex":"F","people":"8928252"},{"year":"1990","age":"45","sex":"M","people":"6848082"},{"year":"1990","age":"45","sex":"F","people":"7115129"},{"year":"1990","age":"50","sex":"M","people":"5553992"},{"year":"1990","age":"50","sex":"F","people":"5899925"},{"year":"1990","age":"55","sex":"M","people":"4981670"},{"year":"1990","age":"55","sex":"F","people":"5460506"},{"year":"1990","age":"60","sex":"M","people":"4953822"},{"year":"1990","age":"60","sex":"F","people":"5663205"},{"year":"1990","age":"65","sex":"M","people":"4538398"},{"year":"1990","age":"65","sex":"F","people":"5594108"},{"year":"1990","age":"70","sex":"M","people":"3429420"},{"year":"1990","age":"70","sex":"F","people":"4610222"},{"year":"1990","age":"75","sex":"M","people":"2344932"},{"year":"1990","age":"75","sex":"F","people":"3723980"},{"year":"1990","age":"80","sex":"M","people":"1342996"},{"year":"1990","age":"80","sex":"F","people":"2545730"},{"year":"1990","age":"85","sex":"M","people":"588790"},{"year":"1990","age":"85","sex":"F","people":"1419494"},{"year":"1990","age":"90","sex":"M","people":"238459"},{"year":"1990","age":"90","sex":"F","people":"745146"},{"year":"2000","age":"0","sex":"M","people":"9735380"},{"year":"2000","age":"0","sex":"F","people":"9310714"},{"year":"2000","age":"5","sex":"M","people":"10552146"},{"year":"2000","age":"5","sex":"F","people":"10069564"},{"year":"2000","age":"10","sex":"M","people":"10563233"},{"year":"2000","age":"10","sex":"F","people":"10022524"},{"year":"2000","age":"15","sex":"M","people":"10237419"},{"year":"2000","age":"15","sex":"F","people":"9692669"},{"year":"2000","age":"20","sex":"M","people":"9731315"},{"year":"2000","age":"20","sex":"F","people":"9324244"},{"year":"2000","age":"25","sex":"M","people":"9659493"},{"year":"2000","age":"25","sex":"F","people":"9518507"},{"year":"2000","age":"30","sex":"M","people":"10205879"},{"year":"2000","age":"30","sex":"F","people":"10119296"},{"year":"2000","age":"35","sex":"M","people":"11475182"},{"year":"2000","age":"35","sex":"F","people":"11635647"},{"year":"2000","age":"40","sex":"M","people":"11320252"},{"year":"2000","age":"40","sex":"F","people":"11488578"},{"year":"2000","age":"45","sex":"M","people":"9925006"},{"year":"2000","age":"45","sex":"F","people":"10261253"},{"year":"2000","age":"50","sex":"M","people":"8507934"},{"year":"2000","age":"50","sex":"F","people":"8911133"},{"year":"2000","age":"55","sex":"M","people":"6459082"},{"year":"2000","age":"55","sex":"F","people":"6921268"},{"year":"2000","age":"60","sex":"M","people":"5123399"},{"year":"2000","age":"60","sex":"F","people":"5668961"},{"year":"2000","age":"65","sex":"M","people":"4453623"},{"year":"2000","age":"65","sex":"F","people":"4804784"},{"year":"2000","age":"70","sex":"M","people":"3792145"},{"year":"2000","age":"70","sex":"F","people":"5184855"},{"year":"2000","age":"75","sex":"M","people":"2912655"},{"year":"2000","age":"75","sex":"F","people":"4355644"},{"year":"2000","age":"80","sex":"M","people":"1902638"},{"year":"2000","age":"80","sex":"F","people":"3221898"},{"year":"2000","age":"85","sex":"M","people":"970357"},{"year":"2000","age":"85","sex":"F","people":"1981156"},{"year":"2000","age":"90","sex":"M","people":"336303"},{"year":"2000","age":"90","sex":"F","people":"1064581"}]
    raw_trace = [
       {"type": "bar", "props": {'x': '0', 'y': '1450376', 'color': 'F', 'column': '1850'}}, 
       {"type": "bar", "props": {'x': '0', 'y': '1483789', 'color': 'M', 'column': '1850'}}
    ]

    result = FalxInterface.synthesize(inputs=[input_data], raw_trace=raw_trace, extra_consts=[], group_results=True)

    for val in result:
        print("#####")
        print(val)
        for p in result[val]:
            print(p[0])
            #print(p[1].to_vl_json())

    
        