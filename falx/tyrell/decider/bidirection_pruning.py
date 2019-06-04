from collections import defaultdict
from typing import cast, Any, Callable, Dict, List, Tuple, Set, FrozenSet
import z3

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

logger = get_logger('tyrell.decider.bidirection_pruning')

class AbstractPrune(GenericVisitor):
    _interp: Interpreter
    _example: Example
    _blames: Set

    def __init__(self, interp: Interpreter, example: Example):
        self._interp = interp
        self._example = example
        self._blames = set()
    
    def is_unsat(self, prog: List[Any]) -> bool:
        ast = prog[0].ast
        prod_name = ast.name
        args = ast.args
        fst_arg = args[0]
        flag = False
        input = robjects.r(self._example.input[0])
        output = robjects.r(self._example.output)

        head_out = set()
        for cname in output.colnames:
            head_out.add(cname)

        content_out = set()
        for o in output:
            content_out.add(o[0])

        head_in = set()
        for cname in input.colnames:
            head_in.add(cname)

        content_in = set()
        for o in input:
            content_in.add(o[0])

        # print('out=====', content_out, head_out, ' in======', content_in, head_in)
        self._blames = set()
        self._blames.add(ast.children[0])
        self._blames.add(ast)

        if prod_name == 'group_by':
            flag = (content_out == content_in)
        elif prod_name == 'select':
            flag =  (content_out < content_in)
        elif prod_name == 'spread':
            key = args[1]
            flag = (int(str(key)) <= len(head_in)) and (content_out <= content_in)
        elif prod_name == 'inner_join':
            flag = content_out.issubset(content_in)
        elif prod_name == 'gather' or prod_name == 'gatherNeg':
            f_list = list(map(int, ast.children[1].data))
            self._blames.add(ast.children[1])
            if any([len(input.colnames) < abs(elem) for elem in f_list]):
                return True

            sel_list = list(o[1] for o in list(filter(lambda x: ((x[0] + 1) in f_list) if f_list[0] > 0  
                              else  (not (-(x[0] + 1) in f_list)), enumerate(input.colnames))))
            flag = any([set(col) == set(sel_list) for col in output])

        elif prod_name == 'mutate':
            flag = content_out.issubset(content_in)
            self._blames.add(ast.children[1])
        elif prod_name == 'unite':
            flag = content_out.issubset(content_in)
            self._blames.add(ast.children[1])
        elif prod_name == 'separate':
            flag = content_out.issubset(content_in)
            self._blames.add(ast.children[1])
        elif prod_name == 'summarise':
            flag = content_out.issubset(content_in)
            self._blames.add(ast.children[1])
        elif prod_name == 'filter':
            flag = content_out < content_in
            self._blames.add(ast.children[1])
        else:
            assert False
        
        return not flag

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
