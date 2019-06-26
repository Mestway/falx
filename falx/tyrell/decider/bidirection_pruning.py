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

logger = get_logger('tyrell.decider.bidirection_pruning')


class AbstractPrune(GenericVisitor):
    _interp: Interpreter
    _example: Example
    _blames: Set
    _input: List 
    _output: List

    def __init__(self, interp: Interpreter, example: Example):
        self._interp = interp
        self._example = example
        self._blames = set()
        self._dummy = 'dummy'
        ## FIXME: multiple inputs!
        input = robjects.r(example.input[0])
        output = robjects.r(example.output)
        self._input = []
        self._output = []
        [self._input.append(col) for col in input]
        [self._output.append(col) for col in output]
    
    
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
        
        if actual == None:
            return False
        
        ### Third, check consistency
        return self.is_consistent(actual, self._output)

    def backward_interp(self, prog: List[Any]):
        per_list = list(itertools.permutations(self._output))
        for out_list in per_list:
            tbl_in = None
            tbl = list(out_list)
            for stmt in reversed(prog):
                error, tbl_in = self.backward_transform(stmt, tbl)
                if error:
                    return error, tbl_in
                if tbl_in == None:
                    break
                tbl = tbl_in
            if self.is_consistent(self._input, tbl_in):
                return False, None

        return False, None
        # return self.backward_transform(prog[-1], self._output)

    def forward_interp(self, prog: List[Any]):
        out = None
        tbl = self._input;

        for stmt in prog:
            error, out = self.forward_transform(stmt, tbl)
            if error: 
                return error, out
            if out == None:
                break
            tbl = out

        return False, out

    def is_consistent(self, actual: List[Any], expect: List[Any]):
        return all([self.is_subset(elem, actual) for elem in expect])

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
        assert not tbl == None, stmt
        ast = stmt.ast
        opcode = ast.name
        args = ast.args
        self._blames.add(ast.children[0])
        self._blames.add(ast)
        error = False
        tbl_size = len(tbl)

        if opcode == 'group_by':
            return error, tbl
        elif opcode == 'filter':
            # assert False
            return error, tbl
        elif opcode == 'select':
            self._blames.add(ast.children[1])
            max_idx = max(list(map(abs, map(int, args[1].data))))
            if max_idx > tbl_size:
                return True, None
            else:
                sel_list = list(map(int, args[1].data))
                tbl_out = [col for idx, col in enumerate(tbl) if self.has_index(sel_list, idx)]
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
            # assert False
            return error, tbl
        elif opcode == 'mutate':
            # assert False
            return error, tbl
        elif opcode == 'summarise':
            # assert False
            return error, tbl
        elif opcode == 'gather' or opcode == 'gatherNeg':
            self._blames.add(ast.children[1])
            max_idx = max(list(map(abs, map(int, args[1].data))))
            if max_idx > tbl_size:
                return True, None
            else:
                sel_list = list(map(int, args[1].data))
                tbl_out = [col for idx, col in enumerate(tbl) if self.has_index(sel_list, idx)]
                return False, tbl_out

        elif opcode == 'spread':
            # assert False
            return error, tbl
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
        tbl_size = len(tbl_out)

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
            col1 = int(args[1].data)
            col2 = int(args[2].data)
            self._blames.add(ast.children[2])
            if col2 > tbl_size:
                return True, None
            else: 
                new_idx = col2 - 1
                if col1 < col2:
                    new_idx = new_idx - 1
                assert new_idx >= 0
                tbl_ret = tbl_out.copy()
                tbl_ret.pop(new_idx)
                return False, tbl_ret
        #Done.
        elif opcode == 'separate':
            col1 = int(args[1].data)
            self._blames.add(ast.children[1])
            if col1 > tbl_size:
                return True, None
            else:
                ex_list = [col1-1, col1]
                tbl_ret = [col for idx, col in enumerate(tbl_out) if not (idx in ex_list)]
                return False, tbl_ret
        elif opcode == 'mutate':
            # self._blames.clear()
            return False, tbl_out
        elif opcode == 'summarise':
            # self._blames.clear()
            return False, tbl_out
        #Done last two columns are new generated.
        elif opcode == 'gather' or opcode == 'gatherNeg':
            return False, tbl_out[:-2]
        elif opcode == 'spread':
            col1 = int(args[1].data)
            col2 = int(args[2].data)
            return False, tbl_out
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
