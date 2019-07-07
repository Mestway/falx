from collections import defaultdict
from typing import cast, Any, Callable, Dict, List, Tuple, Set, FrozenSet
import z3
import itertools

from .assert_violation_handler import AssertionViolationHandler
from .blame import Blame
from .constraint_encoder import ConstraintEncoder
from .example_base import Example, ExampleDecider
from .eval_expr import eval_expr
from .result import ok, bad
from ..spec import TyrellSpec, ValueType
from ..dsl import Node, AtomNode, ParamNode, ApplyNode, NodeIndexer, dfs
from ..interpreter import Interpreter, InterpreterError
from ..logger import get_logger
from ..spec.expr import *
from ..visitor import GenericVisitor
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
    need_spearate2: True

    def __init__(self, interp: Interpreter, example: Example):
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
        self.need_spearate2 = self.compSeparate2()
        # [self._input.append(col) for col in input]
        # [self._output.append(col) for col in output]
    
    
    def is_unsat(self, prog: List[Any]) -> bool:
        ### First, do backward interpretation
        err_back, tbl_in = self.backward_interp(prog)
            
        if err_back:
            # print('prune by backward...')
            return True
        
        ### Second, do forward interpretation
        err_forward, actual = self.forward_interp(prog)

        if err_forward:
            return True
        
        if actual is None:
            return False
        
        ### Third, check consistency
        sat = self.is_consistent(actual, self._output)
        return not sat

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

    def backward_interp(self, prog: List[Any]):
        per_list = list(itertools.permutations(self._output))
        has_error = True
        for out_list in per_list:
            tbl_in = None
            tbl = self._output[list(out_list)]
            for stmt in reversed(prog):
                error, tbl_in = self.backward_transform(stmt, tbl)
                if error:
                    return error, tbl_in
                if tbl_in is None:
                    has_error = False
                    break
                tbl = tbl_in
            
            if self.is_consistent(self._input, tbl_in):
                has_error = False
                break

        return has_error, None
        # return self.backward_transform(prog[-1], self._output)

    def forward_interp(self, prog: List[Any]):
        out = None
        tbl = self._input;

        for stmt in prog:
            error, out = self.forward_transform(stmt, tbl)
            if error: 
                return error, out
            if out is None:
                break
            tbl = out

        return False, out

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
    def forward_transform(self, stmt, tbl):
        # assert not tbl == None, stmt
        ast = stmt.ast
        opcode = ast.name
        args = ast.args
        self._blames.add(ast.children[0])
        self._blames.add(ast)
        error = False
        tbl_size = len(tbl.columns)

        if opcode == 'group_by':
            return error, tbl
        elif opcode == 'filter':
            col_idx = int(args[2].data) - 1
            if col_idx >= len(tbl.dtypes) or np.float64 == tbl.dtypes[col_idx]:
                self._blames.clear()
                self._blames.add(ast.children[2])
                self._blames.add(ast)
                return True, None

            return error, tbl
        elif opcode == 'select':
            self._blames.add(ast.children[1])
            max_idx = max(list(map(abs, map(int, args[1].data))))
            if max_idx > tbl_size:
                return True, None
            else:
                # sel_list = list(map(int, args[1].data))
                sel_list = list(map(lambda x: int(x) - 1, args[1].data))
                cols = tbl.columns
                tbl_out = tbl[cols[sel_list]]
                # tbl_out = [col for idx, col in enumerate(tbl) if self.has_index(sel_list, idx)]
                return False, tbl_out 
        elif opcode == 'unite':
            col1 = int(args[1].data)
            col2 = int(args[2].data)
            self._blames.add(ast.children[1])
            self._blames.add(ast.children[2])
            if col1 > tbl_size or col2 > tbl_size:
                return True, None
            else: 
                return False, None
            
        elif opcode == 'separate':
            # fst_row = tbl.iloc[0, :].values
            # assert False
            return error, None
        elif opcode == 'mutate':
            col1 = int(args[2].data)
            col2 = int(args[3].data)
            if col1 == col2:
                self._blames.add(ast.children[2])
                self._blames.add(ast.children[3])
                return True, None
            return error, None

        elif opcode == 'mutateCustom' or opcode == 'cumsum':
            # assert False
            return error, None
        elif opcode == 'summarise' or opcode == 'groupSum':
            # assert False
            return error, None
        elif opcode == 'gather' or opcode == 'gatherNeg':
            self._blames.add(ast.children[1])
            max_idx = max(list(map(abs, map(int, args[1].data))))
            if max_idx > tbl_size:
                return True, None
            else:
                sel_list = list(map(int, args[1].data))
                if sel_list[0] < 0:
                    sel_list = list(map(lambda x: abs(x) - 1, sel_list))
                    sel_list = [col for col in list(range(0, tbl_size)) if not col in sel_list]
                else: 
                    sel_list = list(map(lambda x: x - 1, sel_list))

                has_numeric = any([np.issubdtype(dt, np.number) for dt in tbl.dtypes[sel_list]])
                has_str = any([(dt == np.object) for dt in tbl.dtypes[sel_list]])
                # print('select types**********', tbl.dtypes[sel_list], tbl.dtypes.values[sel_list])
                # print('sel:', sel_list)
                if has_str and has_numeric:
                    return True, None
                # tbl_out = [col for idx, col in enumerate(tbl) if self.has_index(sel_list, idx)]
                # return False, tbl_out
                return False, None

        elif opcode == 'spread':
            # assert False
            return error, None
        elif opcode == 'inner_join':
            # assert False
            return error, tbl
        else:
            assert False


        return error, None

    ## 1. Mostly for type-checking. 2. Backward abstract interpretation
    def backward_transform(self, stmt, tbl_out):
        ast = stmt.ast
        opcode = ast.name
        args = ast.args
        self._blames.add(ast.children[0])
        self._blames.add(ast)
        error = False
        tbl_in = None
        tbl_size = len(tbl_out.columns)

        ##Done.
        if opcode == 'group_by':
            return False, tbl_out
        ##Done.
        elif opcode == 'filter':
            return False, tbl_out

        ##Done.
        elif opcode == 'select':
            return False, tbl_out
        ##Done.
        elif opcode == 'unite':
            new_col = -1
            fst_row = tbl_out.iloc[0,]
            for idx, item in enumerate(fst_row):
                if isinstance(item, str) and ('_' in item):
                    new_col = idx
                    break

            # assert False, tbl_out
            # for col_vec in tbl_out:
            #     fst_elem = col_vec[0]
            #     if isinstance(col_vec[0], str) and ('-' in fst_elem) and (not str.isdigit(fst_elem.split('-')[0])):
            #         checked = True
            #         break
            
            if new_col == -1:
                self._blames.clear()
                self._blames.add(ast)
                return True, None

            col1 = int(args[1].data)
            col2 = int(args[2].data)
            self._blames.add(ast.children[2])
            if col2 > tbl_size:
                return True, None
            else: 
                assert new_col != -1
                cols = tbl_out.columns.values
                sel_list = [col for idx, col in enumerate(cols) if idx != new_col]
                tbl_ret = tbl_out[sel_list]
                return False, tbl_ret
        #Done.
        elif opcode == 'separate':
            if not self.need_separate:
                return True, None

            self._blames.add(ast.children[1])
            if len(tbl_out) == 0:
                return False, tbl_out
            else:
                cols = tbl_out.columns
                if tbl_out.empty:
                    return False, tbl_out
                tbl_new = tbl_out[[cols[0]]]
                return False, tbl_new
        #Done
        elif opcode == 'mutateCustom':
            any_bool = any([np.issubdtype(dt, np.int32) for dt in tbl_out.dtypes])
            if not any_bool:
                self._blames.clear()
                self._blames.add(ast)
                return True, None

            tbl_ret = tbl_out.iloc[:,:-1]
            return False, tbl_ret
        elif opcode == 'mutate' or opcode == 'cumsum':
            if not self.new_value:
                return True, None

            tbl_ret = tbl_out.iloc[:,:-1]
            return False, tbl_ret
        elif opcode == 'summarise' or opcode == 'groupSum':
            if not self.new_value:
                return True, None

            all_numeric = all([np.issubdtype(dt, np.number) for dt in tbl_out.dtypes])
            if all_numeric:
                self._blames.clear()
                self._blames.add(ast)
                return True, None
                
            tbl_ret = tbl_out.iloc[:,:-1]
            return False, tbl_ret
        #Done last two columns are new generated.
        elif opcode == 'gather' or opcode == 'gatherNeg':
            tbl_ret = tbl_out.iloc[:,:-2]
            return False, tbl_ret
        elif opcode == 'spread':
            col1 = int(args[1].data)
            col2 = int(args[2].data)
            cols = tbl_out.columns.values
            tbl_new = tbl_out[cols[1:]]
            tp = tbl_new.T
            # Hack
            if self.need_spearate2:
                return False, pd.DataFrame()
            return False, tp

            # if len(tbl_out) > 0:
            #     return False, tbl_out[0]
            # else:
            #     return False, []
        #done.
        elif opcode == 'inner_join':
            self._blames.add(ast.children[1])
            return False, tbl_out
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

    def process_examples(self, examples: List[Example], equal_output: Callable[[Any, Any], bool]):
        all_ok = all([self.process_example(example, equal_output) for example in examples])
        if all_ok:
            return ok()
        else:
            blames = self._get_blames()
            if len(blames) == 0:
                return bad()
            else:
                return bad(why=blames)


    def process_example(self, example: Example, equal_output: Callable[[Any, Any], bool]):
        prune = AbstractPrune(self._interp, example)

        if prune.is_unsat(self._prog):
            # If abstract semantics cannot be satisfiable, perform blame analysis
            blame_nodes = prune.get_blame_nodes()
            if blame_nodes is not None:
                self._blames_collection.add(
                    frozenset([(n, n.production) for n in blame_nodes])
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
                 equal_output: Callable[[Any, Any], bool]=lambda x, y: x == y):
        super().__init__(interpreter, examples, equal_output)
        self._assert_handler = AssertionViolationHandler(spec, interpreter)

    def analyze_interpreter_error(self, error: InterpreterError):
        return self._assert_handler.handle_interpreter_error(error)

    def analyze(self, prog):
        blame_finder = BlameFinder(self.interpreter, prog)
        return blame_finder.process_examples(self.examples, self.equal_output)
