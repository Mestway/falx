#!/usr/bin/env python

import argparse
import tyrell.spec as S
from tyrell.interpreter import PostOrderInterpreter, GeneralError
from tyrell.enumerator import BidirectEnumerator
from tyrell.decider import Example, BidirectionalDecider
from tyrell.synthesizer import Synthesizer
from tyrell.logger import get_logger
from rpy2.rinterface import RRuntimeWarning
import rpy2.robjects as robjects
import warnings
import json
import numpy as np

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
    res_id = MorpheusInterpreter().eval(prog[-1].ast, tnames)
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

def subset_eq(actual, expect):
    # logger.info(robjects.r(actual))
    # logger.info(robjects.r(expect))
    row_num, col_num = full_table.get_shape()
    actual_col = len(robjects.r(actual))
    actual_row = len(robjects.r(actual)[0])
    # cmd = 'toJSON({df_name})'.format(df_name=actual)
    # prog_output = robjects.r(cmd)[0]
    all_ok = all([check_row(expect_col, robjects.r(actual)) for expect_col in robjects.r(expect)])
    if all_ok:
        global iter_num
        if actual_row != row_num:
            iter_num = iter_num + 1
            return False
        else:
            logger.info('#Candidates before getting the correct solution: {}'.format(iter_num))
            return True
    else:
        return False

def check_row(col, table):
    all_ok = any(check_col(col, elem) for elem in table)
    return all_ok

def check_col(col1, col2):
    if type(col1) == type(col2):
        if isinstance(col1[0], float):
            col1_r = [round(x, 3) for x in col1]
            col2_r = [round(x, 3) for x in col2]
            return set(col1_r) <= set(col2_r)
        else:
            return set(col1) <= set(col2)
    else:
        try:
            if len(col1) == 0 or len(col2) == 0:
                return False
            if int(col1[0]) and int(col2[0]):
                col1_r = [int(x) for x in col1]
                col2_r = [int(x) for x in col2]
                return set(col1_r) <= set(col2_r)
            else:
                return False
        except ValueError:
            return False

def get_head(df):
    head = set()
    for h in df.colnames:
        head.add(h)

    return head

def get_content(df):
    content = set()
    for vec in df:
        for elem in vec:
            e_val = str(elem)
            content.add(e_val)

    return content



    
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
        _script = '{ret_df} <- {table} %>% filter(.[[{col}]] {op} {const})'.format(
                  ret_df=ret_df_name, table=args[0], op=args[1], col=str(args[2]), const=str(args[3]))
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except:
            logger.error('Error in interpreting filter...')
            raise GeneralError()

    def eval_separate(self, node, args):
        n_cols = robjects.r('ncol(' + args[0] + ')')[0]
        self.assertArg(node, args,
                index=1,
                cond=lambda x: x <= n_cols,
                capture_indices=[0])

        ret_df_name = get_fresh_name()
        _script = '{ret_df} <- separate({table}, {col1}, c("{TMP1}", "{TMP2}"))'.format(
                  ret_df=ret_df_name, table=args[0], col1=str(args[1]), TMP1=get_fresh_col(), TMP2=get_fresh_col())
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

    def eval_summarise(self, node, args):
        input_tbl = robjects.r(args[0])
        input_cols = input_tbl.colnames
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
        row = df.nrow
        if val == 'output':
            row = -1
        return row

    def apply_col(self, val):
        df = robjects.r(val)
        return df.ncol

    def apply_head(self, val):
        curr_df = robjects.r(val)
        curr_head = get_head(curr_df)
        return curr_head

    def apply_content(self, val):
        curr_df = robjects.r(val)
        curr_content = get_content(curr_df)
        return curr_content

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

def synthesize_with_oracle(inputs, sample_output, full_output):
    # TODO: synthesize a program that is not only consistent with the output 
    # but also matches the oracle output
    global full_table 
    full_table = full_output
    return synthesize(inputs, sample_output, full_output)

def synthesize(inputs, output, full_output):
    logger.setLevel('INFO')
    """ synthesizer table transformation programs from input-output examples
    Args:
        inputs: a list of input tables (represented as a list of named tuples)
        output: a symbolic table (of class symbolic.SymTable)
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
    spec = S.parse_file('dsl/morpheus.tyrell')
    logger.info('Parsing succeeded')

    logger.info('Building synthesizer ...')
    for loc in range(1, loc_val + 1):
        synthesizer = Synthesizer(
            #loc: # of function productions
            enumerator=BidirectEnumerator(spec, depth=loc+1, loc=loc),
            decider=BidirectionalDecider(
                spec=spec,
                interpreter=MorpheusInterpreter(),
                examples=[
                    Example(input=['input0'], output='output'),
                ],
                equal_output=subset_eq
            )
        )
        logger.info('Synthesizing programs ...')

        prog = synthesizer.synthesize()
        if prog is not None:
            logger.info('Solution found: {}'.format(prog))
            return [prog]
        else:
            logger.info('Solution not found!')

    return []