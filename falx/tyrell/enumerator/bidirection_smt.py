from z3 import *
from collections import deque
from tyrell.enumerator.enumerator import Enumerator
from functools import reduce
import collections

from tyrell import dsl as D
from tyrell.logger import get_logger

import sys
from pprint import pprint
import numpy as np

logger = get_logger('tyrell.enumerator.bidirection_smt')

# Each statement has opcode, args, and lhs.
class Stmt:
    def __init__(self, opcode, args, lhs):
        self.opcode = opcode
        self.args = args
        self.lhs = lhs
        #FIXME: assuming all statements return tables.
        self.type = 'Table'
        self.ast = None
    
    def __repr__(self):
        if self.ast:
            return str(self.ast)
        else:
            return str(self.lhs) + ' = ' + str(self.opcode) + '(' + str(self.args) + ')'


class BidirectEnumerator(Enumerator):
    # z3 solver
    # z3_solver = Optimize()
    z3_solver = None

    # z3 variables for each production node
    variables = []
    sk_vars = []

    # map from internal k-tree to nodes of program
    program2tree = {}

    def __init__(self, spec, loc=None, component_restriction=None, sketch_restriction=None):
        
        self.z3_solver = Solver()
        custom_list = spec.get_productions_with_lhs('SmallStr')
        if len(custom_list) > 0:
            # Switch to optimizer
            self.z3_solver = Optimize()

        self.variables = []
        self.sk_vars = []
        self.program2tree = {}
        self.spec = spec
        if loc <= 0:
            raise ValueError(
                'LOC cannot be non-positive: {}'.format(loc))
        self.loc = loc
        self.max_children = self.maxChildren()
        self.builder = D.Builder(self.spec)
        self.lines, self.nodes = self.buildKLines(self.max_children, self.loc, self.z3_solver)

        self.model = None
        self.createStmtConstraints()
        self.createDefuseConstraints()

        self.component_restriction = component_restriction
        self.sketch_restriction = sketch_restriction


    def createStmtConstraints(self):
        functions = list(filter(lambda x: x.is_function() and x.id > 0, self.spec.productions()))
        
        custom_fun = []
        for i_loc in range(0, self.loc):
            st = self.lines[i_loc]
            # Opcode has to be one of the high-order functions
            opcode = st.opcode
            ctr_opcode = reduce(lambda a,b: Or(a, b.id == opcode), functions, False)
            self.z3_solver.add(ctr_opcode)
            # nxt_loc = i_loc + 1
            # if nxt_loc < self.loc:
            #     nxt_st = self.lines[nxt_loc]
            #     nxt_opcode = nxt_st.opcode
            #     self.z3_solver.add(nxt_opcode != opcode)

            # All vars defined beforehand.
            def_vars = list(map(lambda x: x.lhs, self.lines[:i_loc]))

            # Each opcode will enforce constraints to its children
            for i in range(0, self.max_children):
                # print('line: ', opcode, ' arg: ', i)
                arg = st.args[i]
                for p in functions:
                    if i < len(p.rhs):
                        child_type = str(p.rhs[i])
                        child_prods = self.spec.get_productions_with_lhs(child_type)
                        if child_type == 'SmallStr':
                            custom_fun.append(p.id)
                        child_prods=list(o.id for o in filter(lambda x: (not x.is_function()), child_prods))
                        if child_type == st.type:
                            child_prods = child_prods + def_vars
                        ctr_arg = reduce(lambda a,b: Or(a, b == arg), child_prods, False)
                        self.z3_solver.add(Implies(opcode == p.id, ctr_arg))
                    else:
                        self.z3_solver.add(Implies(opcode == p.id, arg == -1))

        # Objective function   
        if len(custom_fun) > 0:
            obj_function = 0
            for line in self.lines:
                custom_list = reduce(lambda a,b: Or(a, b == line.opcode), custom_fun, False)
                # print('opcode:', line.opcode, custom_list)
                obj_function = obj_function + If(custom_list, 1, 0) 

            h = self.z3_solver.maximize(obj_function)


    def createDefuseConstraints(self):
        '''All input and intermediate vars will appear at least once in the program'''
        all_args = reduce(lambda a,b: a + b.args, self.lines, [])
        for i in self.spec.get_param_productions():
            ctr_input = reduce(lambda a,b: Or(a, b == i.id), all_args, False)
            self.z3_solver.add(ctr_input)

        if self.loc > 1:
            for i in range(0, self.loc - 1):
                def_var = self.lines[i].lhs
                used_args = reduce(lambda a,b: a + b.args, self.lines[i+1:], [])
                ctr_lhs = reduce(lambda a,b: Or(a, b == def_var), used_args, False)
                self.z3_solver.add(ctr_lhs)

    def maxChildren(self) -> int:
        '''Finds the maximum number of children in the productions'''
        max = 0
        for p in self.spec.productions():
            if len(p.rhs) > max:
                max = len(p.rhs)
        return max

    def buildKLines(self, children, loc, solver):
        lines = []

        for l in range(0,loc):
            lhs_name = 'ret' + str(l)
            lhs = Int(lhs_name)
            opcode_name = 'opcode' + str(l)
            opcode = Int(opcode_name)
            args = []
            for i in range(0, children):
                arg_name = 'arg' + str(i) + '@' + str(l)
                arg_var = Int(arg_name)
                self.variables.append(arg_var)
                args.append(arg_var)
            st = Stmt(opcode, args, lhs)
            lines.append(st)
            self.variables.append(lhs)
            self.variables.append(opcode)
            self.sk_vars.append(opcode)
            self.z3_solver.add(lhs == (1000 + l))

        return lines, None

    def blockModel(self):
        assert(self.model is not None)
        # m = self.z3_solver.model()
        block = []
        # block the model using only the variables that correspond to productions
        for x in self.variables:
            block.append(x != self.model[x])
        ctr = Or(block)
        self.z3_solver.add(ctr)

    def update(self, info=None):
        # TODO: block more than one model
        if info is not None and not isinstance(info, str):
            # blocks models according to provided info (info can be an abstract program inferred)
            for core in info:
                ctr = reduce(lambda a,b: Or(a, self.program2tree[b[0]] != b[1].id), core, False)
                # print('blocking------', ctr)
                self.z3_solver.add(ctr)
        else:
            self.blockModel()

    def buildProgram(self):
        self.program2tree.clear()
        prog = []
        for idx, line in enumerate(self.lines):
            opcode = line.opcode
            opcode_val = self.model[opcode].as_long()
            lhs = idx
            args = []
            children = []

            for arg in line.args:
                arg_val = self.model[arg].as_long()
                if arg_val > 999:
                    args.append(arg_val)
                    c_node = self.lines[arg_val - 1000].ast
                    assert not c_node == None, arg_val
                    children.append(c_node)
                elif arg_val > 0:
                    args.append(arg_val)
                    child_node = self.builder.make_node(arg_val)
                    children.append(child_node)
                    self.program2tree[child_node] = arg
                else: 
                    break

            st = Stmt(opcode_val, args, lhs)
            st.ast = self.builder.make_node(opcode_val, children)
            self.lines[idx].ast = st.ast
            self.program2tree[st.ast] = opcode
            prog.append(st)

        return prog

    def model_to_program(self, model):
        """given a z3 model, consrruct a program out of it """
        prog_to_tree = {}
        prog = []
        ast_at_each_line = []

        for idx, line in enumerate(self.lines):
            opcode = line.opcode
            opcode_val = model[opcode].as_long()
            lhs = idx
            args = []
            children = []

            for arg in line.args:
                arg_val = model[arg].as_long()
                if arg_val > 999:
                    # this refers to an output of a previous line
                    args.append(arg_val)
                    c_node = ast_at_each_line[arg_val - 1000]
                    assert not c_node == None, arg_val
                    children.append(c_node)
                elif arg_val > 0:
                    args.append(arg_val)
                    child_node = self.builder.make_node(arg_val)
                    children.append(child_node)
                    prog_to_tree[child_node] = arg
                else: 
                    break

            st = Stmt(opcode_val, args, lhs)
            st.ast = self.builder.make_node(opcode_val, children)
            ast_at_each_line.append(st.ast)
            prog_to_tree[st.ast] = opcode
            prog.append(st)

        return prog, prog_to_tree

    def next_k_models(self, k):
        """sample next k programs that has different sketches """
        sampled_models = []

        # a list of constraint that will be added to the z3 solver 
        # once tried out these few rounds
        later_to_block = []

        # create a check point for the solver
        self.z3_solver.push()

        while True:
            if len(sampled_models) >= k:
                break

            res = self.z3_solver.check()
            if res == sat:
                model = self.z3_solver.model()
                prog, prog_to_tree = self.model_to_program(model)
                sketch = [stmt.ast.name for stmt in prog]
                
                if self.isBadSketch(sketch):
                    # this sketch is a bad sketch
                    ctr = reduce(lambda a,b: Or(a, b != model[b]), self.sk_vars, False)
                    self.z3_solver.add(ctr)

                    # since we found a real bad sketch, we will save it and apply to the solver
                    later_to_block.append(ctr)
                else:
                    sampled_models.append((model, prog, prog_to_tree))

                # block the z3 solver from generating programs with the same sketch
                sketch_ctr = reduce(lambda a,b: Or(a, b != model[b]), self.sk_vars, False)

                # block the z3 solver from generating the same program (does not restrict same sketch if choose this option)
                full_prog_ctr = reduce(lambda a,x: Or(a, x != model[x]), self.variables, False)

                self.z3_solver.add(sketch_ctr)
            else:
                break

        self.z3_solver.pop()

        for ctr in later_to_block:
            self.z3_solver.add(ctr)

        return sampled_models

    def next(self):
        models = self.next_k_models(10)
        if len(models) == 0:
            return None

        scores = [self.score_program(m[1]) for m in models]
        top_ranked_idx = np.argmax(scores)

        for i, m in enumerate(models):
            sketch = [stmt.ast.name for stmt in m[1]]

        self.model, prog, self.program2tree = models[top_ranked_idx]
        return prog

    def score_program(self, prog):
        """given a program, using the following n-gram model to rank sketches to explore """
        weight_scheme = {
            ('gather', 'gather'): -1.151307, ('gather', 'group_by'): -0.6664353,
            ('gather', 'mutate'): -0.7943757, ('gather', 'separate'): -0.915996,
            ('gather', 'spread'): -1.268881, ('gather', 'summarise'): -2.560551,
            ('gather', 'unite'): -1.193513, ('group_by', 'gather'): -2.900089,
            ('group_by', 'group_by'): -1.67895, ('group_by', 'mutate'): -0.5084593,
            ('group_by', 'separate'): -3.436363, ('group_by', 'spread'): -2.265157,
            ('group_by', 'summarise'): -0.3489752, ('group_by', 'unite'): -3.693064,
            ('mutate', 'gather'): -1.663144, ('mutate', 'group_by'): -0.844439,
            ('mutate', 'mutate'): -1.034842, ('mutate', 'separate'): -2.288105,
            ('mutate', 'spread'): -1.398724, ('mutate', 'summarise'): -1.962134,
            ('mutate', 'unite'): -2.636596, ('separate', 'gather'): -1.168829,
            ('separate', 'group_by'): -0.9445282, ('separate', 'mutate'): -0.9056768,
            ('separate', 'separate'): -0.9110662, ('separate', 'spread'): -0.6616278,
            ('separate', 'unite'): -1.84462, ('spread', 'gather'): -1.782089,
            ('spread', 'group_by'): -1.227245, ('spread', 'mutate'): -1.018238,
            ('spread', 'separate'): -2.60481, ('spread', 'spread'): -1.194322,
            ('spread', 'summarise'): -2.144783, ('spread', 'unite'): -2.609227,
            ('summarise', 'gather'): -2.093432, ('summarise', 'group_by'): -1.018554,
            ('summarise', 'mutate'): -1.214681, ('summarise', 'separate'): -2.682777,
            ('summarise', 'spread'): -1.400691, ('summarise', 'summarise'): -1.547297,
            ('summarise', 'unite'): -3.000444, ('unite', 'gather'): -2.137252, 
            ('unite', 'group_by'): -0.9239298, ('unite', 'mutate'): -0.8130304,
            ('unite', 'separate'): -1.797338, ('unite', 'spread'): -0.3145031, ('unite', 'unite'): -1.285017
        }

        sketch = [stmt.ast.name for stmt in prog]

        if len(sketch) == 1:
            return 1

        score = 0
        for i in range(len(sketch) - 1):
            fst, snd = sketch[i], sketch[i + 1]
            if fst in ["groupSum", "cumsum"]: fst = "summarise"
            if snd in ["groupSum", "cumsum"]: snd = "group_by"
            if fst == "gatherNeg": fst = "gather"
            if snd == "gatherNeg": snd = "gather"
            score += weight_scheme[(fst, snd)]

        #print("{} :: {}".format(sketch, score))
        return score

    # the original next function
    # def next(self):
    #     while True:
    #         self.model = None
    #         res = self.z3_solver.check()
    #         if res == sat:
    #             self.model = self.z3_solver.model()
    #             # print("#########")
    #             # print(self.model)

    #         if self.model is not None:
    #             prog = self.buildProgram()
    #             # Is this a valid sketch?
    #             if self.checkSketch(prog):
    #                 return prog
    #         else:
    #             return None
            
    def checkSketch(self, prog):
        sketch = [stmt.ast.name for stmt in prog]
        
        if self.isBadSketch(sketch):
            self.blockSketch()
            return False
        return True

    def isBadSketch(self, sketch):
        """check if the program sketch is a bad sketch, 
            we will prevent bad sketch directly """

        if self.component_restriction is not None:
            # remove components that does not follow components restriction
            if len([s for s in sketch if s not in self.component_restriction]) > 0:
                return True

        if self.sketch_restriction is not None:
            # remove the sketch if it is in the restricted sketches list
            for restricted_sketch in self.sketch_restriction:
                if (len(restricted_sketch) == sketch 
                    and all([sketch[i] == restricted_sketch[i] for i in range(len(sketch))])):
                    return True

        multi_gathers = [s for s in sketch if 'gather' in s]
        if len(multi_gathers) > 1:
            return True
        
        has_group = 'group_by' in sketch
        has_summarise = 'summarise' in sketch
        if has_group == has_summarise:
            if has_group:
                return (sketch.index('group_by') + 1) != sketch.index('summarise')
        else:
            return True

        # No repetitive component except for separate.
        rep_list = [item for item, count in collections.Counter(sketch).items() if count > 1]
        if len(rep_list) > 0 and (not 'separate' in rep_list):
            # print('bad sketch....', sketch)
            return True

        if ('groupSum') in sketch and (sketch[-1] != 'groupSum'):
            return True
        
        if ('mutateCustom') in sketch and (sketch[-1] != 'mutateCustom'):
            return True

        return False

    def blockSketch(self):
        # block the model using only the variables that correspond to productions
        ctr = reduce(lambda a,b: Or(a, b != self.model[b]), self.sk_vars, False)
        self.z3_solver.add(ctr)