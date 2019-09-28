from collections import defaultdict
from typing import cast, Any, Callable, Dict, List, Tuple, Set, FrozenSet
import z3
import itertools

from falx.tyrell.decider.assert_violation_handler import AssertionViolationHandler
from falx.tyrell.decider.blame import Blame
from falx.tyrell.decider.constraint_encoder import ConstraintEncoder
from falx.tyrell.decider.example_base import Example, ExampleDecider
from falx.tyrell.decider.eval_expr import eval_expr
from falx.tyrell.decider.result import ok, bad
from falx.tyrell.spec import TyrellSpec, ValueType
from falx.tyrell.dsl import Node, AtomNode, ParamNode, ApplyNode, NodeIndexer, dfs
from falx.tyrell.interpreter import Interpreter, InterpreterError
from falx.tyrell.logger import get_logger
from falx.tyrell.spec.expr import *
from falx.tyrell.visitor import GenericVisitor

import rpy2.robjects as robjects

from functools import reduce
import falx.synth_utils
import json
import numpy as np
import pandas as pd

logger = get_logger('tyrell.decider.bidirection_pruning')


class AbstractPrune(GenericVisitor):
    _interp: Interpreter
    _example: Example
    _blames: Set
    _input: None 
    _output: None
    new_value: True
    need_separate: True
    need_separate2: True

    def __init__(self, interp: Interpreter, example: Example, prune: str):
        self._interp = interp
        self._example = example
        self._blames = set()
        self._dummy = 'dummy'
        ## FIXME: multiple inputs!
        input = robjects.r(example.input[0])
        output = robjects.r(example.output)
        self._input = input
        self._output = output
        self.new_value = self.computeNewValue()
        self.need_separate = self.compSeparate()
        self.need_separate2 = self.compSeparate2()
        self.prune = prune
        # [self._input.append(col) for col in input]
        # [self._output.append(col) for col in output]
    
    
    def is_unsat(self, prog: List[Any]) -> bool:
        if self.prune == 'none':
            return False

        ### First, do backward interpretation
        if self.prune == 'falx' or self.prune == 'backward':
            tbl_in_list, abstractions = self.backward_interp(prog)

            has_error = True
            for tbl_in in tbl_in_list:
                if self.is_consistent(self._input, tbl_in):
                    has_error = False
                    break

            if has_error:
                for node in abstractions:
                    self._blames.add(node)

                # print("======= bw")
                # for b in self._blames:
                #     print(b)
                # print("---")

                return True

        ### Second, do forward interpretation
        if self.prune == 'backward':
            return False
        else:
            assert 'forward' == self.prune or 'falx' == self.prune
            actual, abstractions = self.forward_interp(prog)
            
            if actual is "TOP": return False
            if actual is None or not self.is_consistent(actual, self._output): 
                for node in abstractions:
                    self._blames.add(node)

                # print("======= fw")
                # for b in self._blames:
                #     print(b)
                # print("---")
                            
                return True
            
            return False

    def compSeparate(self):
        has_sep = False
        sel_list = [val for val in self._input.columns.values if ('-' in val or '_' in val or '/' in val)]
        has_sep = has_sep or (len(sel_list) > 0)
        for col in self._input.columns:
            if self._input[col].dtype == np.object:
                for vv in self._input[col]:
                    if '-' in vv or '_' in vv or '/' in vv:
                        return True
        return has_sep

    def compSeparate2(self):
        has_sep = False
        for col in self._input.columns:
            if self._input[col].dtype == np.object:
                for vv in self._input[col]:
                    if vv.count('_') == 2:
                        return True
        return has_sep

    def computeNewValue(self):
        in_set = set()
        out_set = set()
        if self._input.shape[1] < 4:
            return True

        for col in self._output.columns:
            if self._output[col].dtype != np.object:
                for vv in self._output[col]:
                    out_set.add(vv)

        for col in self._input.columns:
            if self._input[col].dtype != np.object:
                for vv in self._input[col]:
                    in_set.add(vv)

        diff = out_set - in_set
        return len(diff) > 0

    def bidirectional_abstract_analysis(self, prog):
        # each entry stores the abstract evaluation result of after excuting the i-1 stmt
        temp_tbls = [{"fw_res": None, "bw_res": None} for _ in range(len(prog) + 1)]

        tbl_in = self._input
        temp_tbls[0]["fw_res"] = tbl_in
        for i, stmt in enumerate(prog):
            tbl_out = self.forward_abstract_eval(stmt, tbl_in, "eq")
            tbl_in = tbl_out
            temp_tbls[i + 1]["fw_res"] = tbl_in

        tbl_out = self._output
        temp_tbls[len(prog)]["bw_res"] = tbl_out
        for i, stmt in enumerate(reversed(prog)):
            tbl_in = self.backward_abstract_eval(stmt, tbl_out, "subset_eq")
            tbl_out = tbl_in
            temp_tbls[len(prog) - i - 1]["bw_res"] = tbl_out

        # print("########## BIDIRECTIONAL ")
        # for i in range(len(prog) + 1):
        #     print("fw {}".format(i))
        #     print(temp_tbls[i]["fw_res"])
        #     print("bw {}".format(i))
        #     print(temp_tbls[i]["bw_res"])
        #     pass
        # print("-------------------------")


    def backward_interp(self, prog: List[Any]):
        """apply backward evaluation to prune tables """

        # in order to handle 
        output_table = falx.synth_utils.remove_duplicate_columns(self._output)
        abstractions = []

        tbl_list = [output_table]
        for stmt in reversed(prog):
            tbl_list, abstraction = self.backward_abstract_eval(stmt, tbl_list)
            abstractions.extend(abstraction)
    
            if len(tbl_list) == 0:
                # deductive reasoning results in empty result
                break

        return tbl_list, abstractions


    def forward_interp(self, prog: List[Any]):
        out = None
        tbl = self._input;

        abstractions = []

        for stmt in prog:
            out, abstraction = self.forward_abstract_eval(stmt, tbl)
            abstractions.extend(abstraction)

            if out is None or out is "TOP": 
                break
            else:
                tbl = out

        return out, abstractions

    # 'actual' contains 'expect'
    def is_consistent(self, actual, expect):
        table1 = json.loads(actual.to_json(orient='records'))
        table2 = json.loads(expect.to_json(orient='records'))

        all_ok = falx.synth_utils.check_table_inclusion(table2, table1)
        return all_ok

    def is_primitive(self, var):
        basic_types = (int, str, bool, float)
        return isinstance(var, basic_types)

    def is_subset(self, elem, actual):
        return any([self.is_ok(elem, e) for e in actual])

    def is_ok(self, elem, tgt):
        if tgt == self._dummy:
            return True
        else: 
            return (set(elem) <= set(tgt))

    def has_index(self, sel_list, idx):
        if sel_list[0] > 0:
            return idx in sel_list
        else: 
            abs_list = list(map(abs, sel_list))
            return idx not in abs_list

    ## 1. Type-checking 2. Forward abstract interpretation.
    def forward_abstract_eval(self, stmt, tbl):
        # assert not tbl == None, stmt
        ast = stmt.ast
        opcode, args = ast.name, ast.args

        tbl_size = len(tbl.columns)

        # filter
        if opcode == 'filter':
            col_idx = int(args[2].data) - 1
            if col_idx >= len(tbl.dtypes) or np.float64 == tbl.dtypes[col_idx]:
                return None, [ast, ast.children[2]]
            return tbl, [ast, ast.children[0]]
        # select
        elif opcode == 'select':
            max_idx = max(list(map(abs, map(int, args[1].data))))
            if max_idx > tbl_size:
                return None, [ast, ast.children[0], ast.children[1]]
            else:
                sel_list = list(map(lambda x: int(x) - 1, args[1].data))
                cols = tbl.columns
                tbl_out = tbl[cols[sel_list]]
                return tbl_out, [ast, ast.children[0], ast.children[1]]
        # unite
        elif opcode == 'unite':
            col1 = int(args[1].data)
            col2 = int(args[2].data)
            if col1 > tbl_size or col2 > tbl_size:
                return None, [ast, ast.children[0], ast.children[1], ast.children[2]]
            else:
                return "TOP", [ast, ast.children[0]]
        # separate
        elif opcode == 'separate':
            if int(args[1].data) > tbl_size:
                return None, [ast, ast.children[0], ast.children[1]]

            # check if there is entry containing a separator
            col_idx = int(args[1].data) - 1
            col = tbl[tbl.columns[col_idx]]
            test_val = col[0]
            if not ((col.dtype == np.object) and ('_' in test_val or '-' in test_val  or '/' in test_val)):
                return None, [ast, ast.children[0], ast.children[1]]

            return "TOP", [ast, ast.children[0]]
        # mutate
        elif opcode == 'mutate':
            col1 = int(args[2].data)
            col2 = int(args[3].data)
            if col1 == col2:
                return None, [ast, ast.children[0], ast.children[2], ast.children[3]]
            return "TOP", [ast, ast.children[0]]
        # cumsum
        elif opcode == 'cumsum':
            if int(args[1].data) > tbl_size:
                return None, [ast, ast.children[0], ast.children[1]]

            col_idx = int(args[1].data) - 1
            col = tbl[tbl.columns[col_idx]]
            if not np.issubdtype(col.dtype, np.number):
                return None, [ast, ast.children[0], ast.children[1]]
                
            return "TOP", [ast, ast.children[0]]
        # mutateCustom
        elif opcode == 'mutateCustom':
            return "TOP", [ast, ast.children[0]]
        # summarise
        elif opcode == 'summarise' or opcode == 'groupSum':
            return "TOP", [ast, ast.children[0]]
        # gather/gatherNeg
        elif opcode == 'gather' or opcode == 'gatherNeg':
            max_idx = max(list(map(abs, map(int, args[1].data))))
            if max_idx > tbl_size:
                # return false if index out of bound
                return None, [ast, ast.children[0], ast.children[1]]
            else:
                sel_list = list(map(int, args[1].data))
                if sel_list[0] < 0:
                    sel_list = list(map(lambda x: abs(x) - 1, sel_list))
                    sel_list = [col for col in list(range(0, tbl_size)) if not col in sel_list]
                else:
                    sel_list = list(map(lambda x: x - 1, sel_list))

                has_numeric = any([np.issubdtype(dt, np.number) for dt in tbl.dtypes[sel_list]])
                has_str = any([(dt == np.object) for dt in tbl.dtypes[sel_list]])

                if has_str and has_numeric:
                    return None, [ast, ast.children[0], ast.children[1]]

                return "TOP", [ast, ast.children[0], ast.children[1]]

        elif opcode == 'spread':
            if int(args[1].data) > tbl_size:
                return None, [ast, ast.children[0], ast.children[1]]

            if int(args[2].data) > tbl_size:
                return None, [ast, ast.children[0], ast.children[2]]

            col_idx = int(args[1].data) - 1
            col = tbl[tbl.columns[col_idx]]
            if np.issubdtype(col.dtype, np.number):
                return None, [ast, ast.children[0], ast.children[1]]

            return "TOP", [ast, ast.children[0]]
        else:
            assert False

        return "TOP", [ast, ast.children[0]]


    def backward_abstract_eval(self, stmt, tbl_out_list):
        """backward reasoning with lazy abstraction 
        Given a statement stmt and a list of tbl_out,
        this function calculates properties of inputs to the stmt:
        it returns a list of input tables, 
        such that the true input table should contain as least one fo them
        """
        ast = stmt.ast
        opcode, args = ast.name, ast.args

        # abstraction used for the backward analysis, 
        # by default, we only use ast and it's first child
        abstraction = [ast, ast.children[0]]

        # obtain bot from backward inference if we already obtain bot
        for tbl_out in tbl_out_list:
            if tbl_out.empty:
                return [pd.DataFrame()], abstraction

        ##Done.
        if opcode == 'filter':
            return tbl_out_list, abstraction
        ##Done.
        elif opcode == 'select':
            return tbl_out_list, abstraction
        ##Done.
        elif opcode == 'unite':
            tbl_in_list = []
            for tbl_out in tbl_out_list:
                new_col = -1

                # use the first row to find which column is obtained from unite
                fst_row = tbl_out.iloc[0,]
                for idx, item in enumerate(fst_row):
                    if isinstance(item, str) and ('_' in item):
                        new_col = idx
                        break

                if new_col == -1:
                    # this branch failed, continue to examine the next branch
                    # so that we won't get a table for the next layer
                    continue
                else:
                    tbl_size = len(tbl_out.columns)
                    if int(args[2].data) > tbl_size:
                        # return empty because we already find an error
                        return [], abstraction + [ast.children[2]]

                    cols = tbl_out.columns.values
                    sel_list = [col for idx, col in enumerate(cols) if idx != new_col]
                    tbl_ret = tbl_out[sel_list]
                    tbl_in_list.append(tbl_ret)
            
            return tbl_in_list, abstraction
        #Done.
        elif opcode == 'separate':
            if not self.need_separate:
                return [], abstraction
            tbl_in_list = []
            abstraction = [ast, ast.children[0]]
            for tbl_out in tbl_out_list:

                cols = tbl_out.columns
                if len(cols) < 2:
                    return [pd.DataFrame()], abstraction

                # enumerate candidate key-value columns
                for sep_cols in itertools.combinations(cols, 2):
                    tbl_new = tbl_out[[x for x in cols if x not in sep_cols]]
                    tbl_in_list.append(tbl_new)

            return tbl_in_list, abstraction
        #Done
        elif opcode == 'mutateCustom' or opcode == 'mutate' or opcode == 'cumsum' or opcode == 'groupSum':
            # remove unused cases

            if not self.new_value:
                return [], abstraction

            tbl_in_list = []
            for tbl_out in tbl_out_list:
                
                if opcode == "mutateCustom":
                    # requires that there exists a boolean field for mutateCustom operator
                    any_bool = any([np.issubdtype(dt, np.int32) for dt in tbl_out.dtypes])
                    if not any_bool:
                       continue
                
                if opcode in ["groupSum"]:
                    # requires that there exists a least a non-numerical field
                    all_numeric = all([np.issubdtype(dt, np.number) for dt in tbl_out.dtypes])
                    if all_numeric:
                        continue

                cols = tbl_out.columns
                # enumerate all possible newly generated columns
                for i, col in enumerate(cols):
                    if np.issubdtype(tbl_out.dtypes[i], np.number):
                        tbl_new = tbl_out[[x for x in cols if x != col]]
                        tbl_in_list.append(tbl_new)

            return tbl_in_list, abstraction
        #Done
        elif opcode == 'gather' or opcode == 'gatherNeg':
            tbl_in_list = []
            for tbl_out in tbl_out_list:
                cols = tbl_out.columns
                if len(cols) < 2:
                    # in case the table contain less than two rows, 
                    # it is possile that the last row is newly generately, 
                    # so we'll infer BOT to the synthesizer (thus return pd.DataFrame() to bail from bw inference)
                    tbl_in_list.append(pd.DataFrame())
                    break
                # enumerate candidate key-value columns
                for key_val_cols in itertools.combinations(cols, 2):
                    tbl_new = tbl_out[[x for x in cols if x not in key_val_cols]]
                    tbl_in_list.append(tbl_new)

            return tbl_in_list, abstraction
        # spread
        elif opcode == 'spread':
            # TODO: this reasoning is expensive
            tbl_in_list = []
            for tbl_out in tbl_out_list:
                cols = tbl_out.columns
                
                tbl_new = pd.melt(tbl_out, id_vars=[], value_vars=cols, var_name='varNameColumn')
                
                # case 1: the id column is gone
                tbl_in_list.append(tbl_new[[c for c in tbl_new.columns if c != "varNameColumn"]])

                # case 2: the id column is there, enumerate all possible id columns
                for id_col in cols:
                    tbl_new = pd.melt(tbl_out, id_vars=[id_col], 
                                      value_vars=[c for c in cols if c != id_col],
                                      var_name='varNameColumn')
                    tbl_in_list.append(tbl_new[[c for c in tbl_new.columns if c != "varNameColumn"]])
       
            return tbl_in_list, abstraction
        else:
            assert False

    def get_blame_nodes(self):
        return self._blames


class ConstraintInterpreter(GenericVisitor):
    _interp: Interpreter
    _inputs: Example

    def __init__(self, interp: Interpreter, inputs: List[Any]):
        self._interp = interp
        self._inputs = inputs

    def interpret(self, prog: List[Any]):
        return self.visit(prog[-1].ast)

    def visit_atom_node(self, atom_node: AtomNode):
        return self._interp.eval(atom_node, self._inputs)

    def visit_param_node(self, param_node: ParamNode):
        return self._interp.eval(param_node, self._inputs)

    def visit_apply_node(self, apply_node: ApplyNode):
        in_values = [self.visit(x) for x in apply_node.args]
        method_name = self._eval_method_name(apply_node.name)
        method = getattr(self._interp, method_name, None)
        if method is None:
            raise NotImplementedError(
                'Cannot find the required eval method: {}'.format(method_name))
        method_output = method(apply_node, in_values)

        return method_output

    @staticmethod
    def _eval_method_name(name):
        return 'eval_' + name

    @staticmethod
    def _apply_method_name(name):
        return 'apply_' + name


class BlameFinder:
    _interp: Interpreter
    _prog: Node
    _indexer: NodeIndexer
    _blames_collection: Set[FrozenSet[Blame]]

    def __init__(self, interp: Interpreter, prog: Node):
        self._interp = interp
        self._prog = prog
        # self._indexer = NodeIndexer(prog)
        self._blames_collection = set()

    def _get_raw_blames(self) -> List[List[Blame]]:
        return [list(x) for x in self._blames_collection]

    def _get_blames(self) -> List[List[Blame]]:
        return [list(x) for x in self._blames_collection]

    def process_examples(self, examples: List[Example], equal_output: Callable[[Any, Any], bool], prune: str):
        all_ok = all([self.process_example(example, equal_output, prune) for example in examples])
        if all_ok:
            return ok()
        else:
            blames = self._get_blames()
            if len(blames) == 0:
                return bad()
            else:
                return bad(why=blames)

    def process_example(self, example: Example, equal_output: Callable[[Any, Any], bool], prune: str):
        prune = AbstractPrune(self._interp, example, prune)

        if prune.is_unsat(self._prog):
            # If abstract semantics cannot be satisfiable, perform blame analysis
            blame_nodes = prune.get_blame_nodes()

            if blame_nodes is not None:
                self._blames_collection.add(
                    frozenset([Blame(n, n.production) for n in blame_nodes])
                )
            return False
        else:
            # If abstract semantics is satisfiable, start interpretation
            constraint_interpreter = ConstraintInterpreter(self._interp, example.input)
            interpreter_output = constraint_interpreter.interpret(self._prog)
            return equal_output(interpreter_output, example.output)


class BidirectionalDecider(ExampleDecider):
    assert_handler: AssertionViolationHandler

    def __init__(self,
                 spec: TyrellSpec,
                 interpreter: Interpreter,
                 examples: List[Example],
                 prune: str,
                 equal_output: Callable[[Any, Any], bool]=lambda x, y: x == y):
        super().__init__(interpreter, examples, equal_output)
        self._assert_handler = AssertionViolationHandler(spec, interpreter)
        self.prune = prune

    def analyze_interpreter_error(self, error: InterpreterError):
        return self._assert_handler.handle_interpreter_error(error)

    def analyze(self, prog):
        blame_finder = BlameFinder(self.interpreter, prog)
        res = blame_finder.process_examples(self.examples, self.equal_output, self.prune)
        return res
