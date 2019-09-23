#!/usr/bin/env python
import argparse
import os

import tyrell.spec as S
from tyrell.interpreter.post_order import PostOrderInterpreter, GeneralError
from tyrell.enumerator.smt import SmtEnumerator
from falx.tyrell.enumerator.bidirection_smt import BidirectEnumerator
from tyrell.decider.example_base import Example
from falx.tyrell.decider.bidirection_pruning import BidirectionalDecider
from tyrell.decider.example_constraint_pruning import ExampleConstraintPruningDecider
from tyrell.synthesizer.synthesizer import Synthesizer
from tyrell.logger import get_logger

from rpy2.rinterface import RRuntimeWarning
import rpy2.robjects as robjects
from rpy2.robjects import pandas2ri
pandas2ri.activate()
import warnings
import json
import numpy as np
import pandas as pd
from itertools import combinations 

from falx import synth_utils

# suppress R warnings
warnings.filterwarnings("ignore", category=RRuntimeWarning)

logger = get_logger('tyrell')

counter_ = 1

full_table = None

#library(compare)
robjects.r('''
    library(dplyr)
    library(tidyr)
    library(jsonlite)
   ''')

def default(o):
    if isinstance(o, np.int64): return int(o)  
    raise TypeError

def evaluate(prog, inputs):
    """ evaluate a table transformation program on input tables
    Args:
        input: a list of input tables (represented as a list of named tuples)
        prog: a R program
    Returns:
        an output table (represented as a list of named tuples)
    """
    tnames = []
    for i in range(len(inputs)):
        name = "input_{}".format(i)
        tnames.append(name)
        init_tbl_json_str(name, json.dumps(inputs[i], default=default))

    # call morpheusInterpreter to obtain result variable name in r
    if type(prog) is list:
        res_id = MorpheusInterpreter().eval(prog[-1].ast, tnames)
    else:
        res_id = MorpheusInterpreter().eval(prog, tnames)

    # get the result out from r environment
    prog_output = robjects.r('toJSON({})'.format(res_id))[0]
    return json.loads(prog_output)

## Common utils.
def get_collist(sel):
    sel_str = ",".join(sel)
    return "c(" + sel_str + ")"

def get_fresh_name():
    global counter_ 
    counter_ = counter_ + 1

    fresh_str = 'RET_DF' + str(counter_)
    return fresh_str

def get_fresh_col():
    global counter_ 
    counter_ = counter_ + 1

    fresh_str = 'COL' + str(counter_)
    return fresh_str

def get_type(df, index):
    _rscript = 'sapply({df_name}, class)[{pos}]'.format(df_name=df, pos=index)
    ret_val = robjects.r(_rscript)
    return ret_val[0]

iter_num = 0

# Only for no pruning 
def proj_eq(actual, expect):
    table2 = robjects.r('toJSON({df_name})'.format(df_name=actual))[0]
    table2 = json.loads(table2)

    table1 = robjects.r('toJSON({df_name})'.format(df_name=expect))[0]
    table1 = json.loads(table1)

    row_num, col_num = full_table.get_shape()
    actual_tbl = robjects.r(actual)
    actual_col = actual_tbl.shape[1]
    actual_row = actual_tbl.shape[0]

    expect_col = robjects.r(expect).shape[1]

    if actual_col < expect_col:
        return False
    else:
        domain = range(actual_col)
        candidates = list(combinations(domain, expect_col))
        for sel_list in candidates:
            sel_list = list(sel_list)
            cols = actual_tbl.columns
            proj_out = actual_tbl[cols[sel_list]]
            table2 = json.loads(proj_out.to_json(orient='records'))

            all_ok = synth_utils.align_table_schema(table1, table2) != None

            if all_ok:
                global iter_num
                full_table_ok = synth_utils.align_table_schema(full_table.values, table2, check_equivalence=True, boolean_result=True)

                if not full_table_ok:
                    iter_num = iter_num + 1
                    return False
                else:
                    logger.info('# candidates before getting the correct solution: {}'.format(iter_num))
                    print('# candidates before getting the correct solution: {}'.format(iter_num))
                    return True

        return False
            

def subset_eq(actual, expect):
    """check whether the actual table is a subset of expect table """
    table2 = robjects.r('toJSON({df_name})'.format(df_name=actual))[0]
    table1 = robjects.r('toJSON({df_name})'.format(df_name=expect))[0]
    table1 = json.loads(table1)
    table2 = json.loads(table2)

    actual_col = robjects.r(actual).shape[1]
    actual_row = robjects.r(actual).shape[0]

    all_ok = synth_utils.align_table_schema(table1, table2) != None

    if all_ok:
        global iter_num
        
        if full_table is None:
            # need to work with this to get more solutions
            iter_num = iter_num + 1
            return True

        full_table_ok = synth_utils.align_table_schema(full_table.values, table2, check_equivalence=True, boolean_result=True)

        if not full_table_ok:
            iter_num = iter_num + 1
            return False
        else:
            logger.info('# candidates before getting the correct solution: {}'.format(iter_num))
            print('# candidates before getting the correct solution: {}'.format(iter_num))
            return True

    return False

    
class MorpheusInterpreter(PostOrderInterpreter):
    ## Concrete interpreter
    def eval_ColInt(self, v):
        return int(v)

    def eval_ColList(self, v):
        return v

    def eval_const(self, node, args):
        return args[0]

    def eval_select(self, node, args):
        n_cols = robjects.r('ncol(' + args[0] + ')')[0]
        self.assertArg(node, args,
                index=1,
                cond=lambda x: max(list(map(lambda y: int(y), x))) <= n_cols,
                capture_indices=[0])

        ret_df_name = get_fresh_name()
        _script = '{ret_df} <- select({table}, {cols})'.format(
                   ret_df=ret_df_name, table=args[0], cols=get_collist(args[1]))
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except:
            logger.error('Error in interpreting select...')
            raise GeneralError()

    def eval_unite(self, node, args):
        n_cols = robjects.r('ncol(' + args[0] + ')')[0]
        first_idx = int(args[1])
        self.assertArg(node, args,
                index=1,
                cond=lambda x: x <= n_cols,
                capture_indices=[0])
        self.assertArg(node, args,
                index=2,
                cond=lambda x: x <= n_cols and x != first_idx,
                capture_indices=[0, 1])

        ret_df_name = get_fresh_name()
        _script = '{ret_df} <- unite({table}, {TMP}, {col1}, {col2})'.format(
                  ret_df=ret_df_name, table=args[0], TMP=get_fresh_col(), col1=str(args[1]), col2=str(args[2]))
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except:
            logger.error('Error in interpreting unite...')
            raise GeneralError()

    def eval_filter(self, node, args):
        n_cols = robjects.r('ncol(' + args[0] + ')')[0]
        self.assertArg(node, args,
                index=2,
                cond=lambda x: x <= n_cols,
                capture_indices=[0])
        self.assertArg(node, args,
                index=2,
                cond=lambda x: get_type(args[0], str(x)) != 'factor',
                capture_indices=[0])

        ret_df_name = get_fresh_name()
        _script = '{ret_df} <- {table} %>% filter(.[[{col}]] {op} "{const}")'.format(
                  ret_df=ret_df_name, table=args[0], op=args[1], col=str(args[2]), const=str(args[3]))
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except Exception as e:
            logger.error('Error in interpreting filter...', e)
            raise GeneralError()

    def eval_separate(self, node, args):
        n_cols = robjects.r('ncol(' + args[0] + ')')[0]
        self.assertArg(node, args,
                index=1,
                cond=lambda x: x <= n_cols,
                capture_indices=[0])

        tbl = robjects.r(args[0])
        col = tbl.columns[int(args[1]) - 1]
        ret_df_name = get_fresh_name()
        _script = '{ret_df} <- separate({table}, {col1}, c("{TMP1}", "{TMP2}"))'.format(
                  ret_df=ret_df_name, table=args[0], col1=str(args[1]), TMP1=get_fresh_col(), TMP2=get_fresh_col())
        if tbl[col].dtype == np.object:
            cell = tbl[col][0]
            if cell.count('_') > 1:
                _script = '{ret_df} <- separate({table}, {col1}, c("{TMP1}", "{TMP2}", "{TMP3}"), sep="_")'.format(
                  ret_df=ret_df_name, table=args[0], col1=str(args[1]), TMP1=get_fresh_col(), TMP2=get_fresh_col(), TMP3=get_fresh_col())
        else:
            raise GeneralError()

        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except:
            logger.error('Error in interpreting separate...')
            raise GeneralError()

    def eval_spread(self, node, args):
        n_cols = robjects.r('ncol(' + args[0] + ')')[0]
        first_idx = int(args[1])
        self.assertArg(node, args,
                index=1,
                cond=lambda x: x <= n_cols,
                capture_indices=[0])
        self.assertArg(node, args,
                index=2,
                cond=lambda x: x <= n_cols and x > first_idx,
                capture_indices=[0, 1])

        ret_df_name = get_fresh_name()
        _script = '{ret_df} <- spread({table}, {col1}, {col2})'.format(
                  ret_df=ret_df_name, table=args[0], col1=str(args[1]), col2=str(args[2]))
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except:
            logger.error('Error in interpreting spread...')
            raise GeneralError()

    def eval_gather(self, node, args):
        n_cols = robjects.r('ncol(' + args[0] + ')')[0]
        self.assertArg(node, args,
                index=1,
                cond=lambda x: max(list(map(lambda y: int(y), x))) <= n_cols,
                capture_indices=[0])

        ret_df_name = get_fresh_name()
        _script = '{ret_df} <- gather({table}, KEY, VALUE, {cols})'.format(
                   ret_df=ret_df_name, table=args[0], cols=get_collist(args[1]))
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except:
            logger.error('Error in interpreting gather...')
            raise GeneralError()

    def eval_gatherNeg(self, node, args):
        return self.eval_gather(node, args)

    def eval_group_by(self, node, args):
        n_cols = robjects.r('ncol(' + args[0] + ')')[0]
        self.assertArg(node, args,
                index=1,
                cond=lambda x: max(list(map(lambda y: int(y), x))) <= n_cols,
                capture_indices=[0])
        # self.assertArg(node, args,
        #         index=1,
        #                cond=lambda x: len(x) == 1,
        #         capture_indices=[0])

        ret_df_name = get_fresh_name()
        _script = '{ret_df} <- group_by_at({table}, {cols})'.format(
                   ret_df=ret_df_name, table=args[0], cols=get_collist(args[1]))
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except:
            logger.error('Error in interpreting group_by...')
            raise GeneralError()

    def eval_groupSum(self, node, args):
        input_tbl = robjects.r(args[0])
        input_cols = input_tbl.columns.values
        n_cols = len(input_cols)

        self.assertArg(node, args,
                index=3,
                cond=lambda x: max(list(map(lambda y: int(y), x))) <= n_cols,
                capture_indices=[0])

        aggr_fun = str(args[1])
        self.assertArg(node, args,
                index=2,
                cond=lambda x: x <= n_cols,
                capture_indices=[0])

        if not aggr_fun == 'n':
            self.assertArg(node, args,
                    index=2,
                    cond=lambda x: get_type(args[0], str(x)) == 'integer' or get_type(args[0], str(x)) == 'numeric',
                    capture_indices=[0])

        ret_df_name = get_fresh_name()
        _script = ''
        if aggr_fun == 'n':
            _script = '{ret_df} <- group_by_at({table}, {cols})  %>% summarise({TMP} = {aggr} ())'.format(
                    ret_df=ret_df_name, table=args[0], TMP=get_fresh_col(), aggr=aggr_fun, cols=get_collist(args[3]))
        else:
            aggr_col = input_cols[args[2]-1]
            _script = '{ret_df} <- group_by_at({table}, {cols}) %>% summarise({TMP} = {aggr} (`{col}`))'.format(
                    ret_df=ret_df_name, table=args[0], TMP=get_fresh_col(), aggr=aggr_fun, col=aggr_col, cols=get_collist(args[3]))
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except Exception as e:
            logger.error('Error in interpreting eval_groupSum...')
            raise GeneralError()

    def eval_summarise(self, node, args):
        input_tbl = robjects.r(args[0])
        input_cols = input_tbl.columns.values
        n_cols = len(input_cols)

        aggr_fun = str(args[1])
        self.assertArg(node, args,
                index=2,
                cond=lambda x: x <= n_cols,
                capture_indices=[0])

        if not aggr_fun == 'n':
            self.assertArg(node, args,
                    index=2,
                    cond=lambda x: get_type(args[0], str(x)) == 'integer' or get_type(args[0], str(x)) == 'numeric',
                    capture_indices=[0])

        ret_df_name = get_fresh_name()
        _script = ''
        if aggr_fun == 'n':
            _script = '{ret_df} <- {table} %>% summarise({TMP} = {aggr} ())'.format(
                    ret_df=ret_df_name, table=args[0], TMP=get_fresh_col(), aggr=aggr_fun)
        else:
            aggr_col = input_cols[args[2]-1]
            _script = '{ret_df} <- {table} %>% summarise({TMP} = {aggr} (`{col}`))'.format(
                    ret_df=ret_df_name, table=args[0], TMP=get_fresh_col(), aggr=aggr_fun, col=aggr_col)
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except Exception as e:
            logger.error('Error in interpreting summarise...')
            raise GeneralError()

    def eval_mutateCustom(self, node, args):
        n_cols = robjects.r('ncol(' + args[0] + ')')[0]
        col_idx = args[2] - 1
        self.assertArg(node, args,
                index=2,
                cond=lambda x: x <= n_cols,
                capture_indices=[0])

        input_tbl = robjects.r(args[0])
        col_type = input_tbl.dtypes[col_idx]
        if col_type == np.float64 or col_type == np.int64:
            raise GeneralError()

        ret_df_name = get_fresh_name()
        _script = '{ret_df} <- {table} %>% mutate({TMP}=(.[[{col1}]] {op} "{col2}"))'.format(
                  ret_df=ret_df_name, table=args[0], TMP=get_fresh_col(), op=args[1], col1=str(args[2]), col2=str(args[3]))
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except Exception as e:
            logger.error('Error in interpreting mutateCustom...', _script)
            # assert False, e
            raise GeneralError()

    def eval_cumsum(self, node, args):
        n_cols = robjects.r('ncol(' + args[0] + ')')[0]
        self.assertArg(node, args,
                index=1,
                cond=lambda x: x <= n_cols,
                capture_indices=[0])

        ret_df_name = get_fresh_name()
        _script = '{ret_df} <- {table} %>% mutate({TMP}=cumsum(.[[{col1}]]))'.format(
                  ret_df=ret_df_name, table=args[0], TMP='cumsum', col1=str(args[1]))
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except Exception as e:
            logger.error('Error in interpreting cumsum...', _script)
            raise GeneralError()

    def eval_mutate(self, node, args):
        n_cols = robjects.r('ncol(' + args[0] + ')')[0]
        self.assertArg(node, args,
                index=2,
                cond=lambda x: x <= n_cols,
                capture_indices=[0])
        self.assertArg(node, args,
                index=3,
                cond=lambda x: x <= n_cols,
                capture_indices=[0])
        self.assertArg(node, args,
                index=2,
                cond=lambda x: get_type(args[0], str(x)) == 'numeric',
                capture_indices=[0])
        self.assertArg(node, args,
                index=3,
                cond=lambda x: get_type(args[0], str(x)) == 'numeric',
                capture_indices=[0])

        ret_df_name = get_fresh_name()
        _script = '{ret_df} <- {table} %>% mutate({TMP}=.[[{col1}]] {op} .[[{col2}]])'.format(
                ret_df=ret_df_name, table=args[0], TMP='mutate_a', op=args[1], col1=str(args[2]), col2=str(args[3]))
        # _script = '{ret_df} <- {table} %>% mutate({TMP}=.[[{col1}]] {op} .[[{col2}]])'.format(
        #           ret_df=ret_df_name, table=args[0], TMP=get_fresh_col(), op=args[1], col1=str(args[2]), col2=str(args[3]))
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except:
            logger.error('Error in interpreting mutate...')
            raise GeneralError()

    def eval_inner_join(self, node, args):
        ret_df_name = get_fresh_name()
        _script = '{ret_df} <- inner_join({t1}, {t2})'.format(
                  ret_df=ret_df_name, t1=args[0], t2=args[1])
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except:
            logger.error('Error in interpreting innerjoin...')
            raise GeneralError()

    ## Abstract interpreter
    def apply_row(self, val):
        df = robjects.r(val)
        return df.shape[0]

    def apply_col(self, val):
        df = robjects.r(val)
        return df.shape[1]


def init_tbl_json_str(df_name, json_loc):
    cmd = '''
    # tbl_name <- read.csv(csv_location, check.names = FALSE)
    tbl_name <- fromJSON(json_location)
    fctr.cols <- sapply(tbl_name, is.factor)
    int.cols <- sapply(tbl_name, is.integer)
    tbl_name[, fctr.cols] <- sapply(tbl_name[, fctr.cols], as.character)
    tbl_name[, int.cols] <- sapply(tbl_name[, int.cols], as.numeric)
    '''
    cmd = cmd.replace('tbl_name', df_name).replace('json_location', "'" + json_loc + "'")
    try:
        robjects.r(cmd)
    except:
        print('Parse error!!! Move on...')
    return None


def synthesize(inputs, output, oracle_output, prune, extra_consts, grammar_base_file):

    global full_table 
    full_table = oracle_output

    # level can be DEBUG or INFO
    logger.setLevel('INFO')
    """ synthesizer table transformation programs from input-output examples
    Args:
        inputs: a list of input tables (represented as a list of named tuples)
        output: a symbolic table (of class symbolic.SymTable)
        full_output:  the oracle output table, the task would need to generalize to it
        extra_consts: extra constants provided to the solver
    Returns:
        a list of transformation programs s.t. p(inputs) = output
    """
    
    #print("output table:\n", output)
    #print("input table:\n", inputs[0])
    loc_val = 2
    output_data = json.dumps(output.instantiate())
    input_data = json.dumps(inputs[0], default=default)
    init_tbl_json_str('input0', input_data)
    init_tbl_json_str('output', output_data)

    print(robjects.r('input0'))
    print(robjects.r('output'))

    depth_val = loc_val + 1
    logger.info('Parsing spec ...')

    # provide additional string constants to the solver
    grammar_base = grammar_base_file
    grammar_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dsl", "__tidyverse__.tyrell")
    synth_utils.update_search_grammar(extra_consts, grammar_base, grammar_file)

    spec = S.parse_file(grammar_file)
    logger.info('Parsing succeeded')

    logger.info('Building synthesizer ...')
    global iter_num
    iter_num = 0
    for loc in range(1, loc_val + 1):
        eq_fun = subset_eq
        if prune == 'none':
            eq_fun = proj_eq

        enumerator = BidirectEnumerator(spec, depth=loc+1, loc=loc)
        decider=BidirectionalDecider(
                spec=spec,
                interpreter=MorpheusInterpreter(),
                examples=[
                    Example(input=['input0'], output='output'),
                ],
                prune=prune,
                equal_output=eq_fun
            )

        synthesizer = Synthesizer(enumerator=enumerator, decider=decider)
        logger.info('Synthesizing programs ...')

        prog = synthesizer.synthesize()
        if prog is not None:
            logger.info('Solution found: {}'.format(prog))
            return [prog]
        else:
            logger.info('Solution not found!')

    return []