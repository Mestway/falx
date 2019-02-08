#!/usr/bin/env python

import tyrell.spec as S
from tyrell.interpreter import PostOrderInterpreter, GeneralError
from tyrell.enumerator import SmtEnumerator
from tyrell.decider import Example, ExampleConstraintDecider
from tyrell.synthesizer import Synthesizer
from tyrell.logger import get_logger
import rpy2.robjects as robjects
import rpy2.rinterface as ri 
from rpy2.rinterface import RRuntimeWarning

import itertools
import json
import os
import warnings


# suppress R warnings
warnings.filterwarnings("ignore", category=RRuntimeWarning)

logger = get_logger('tyrell')

counter_ = 1

robjects.r('''
    library(dplyr)
    library(tidyr)
    library(jsonlite)
   ''')

g_list = []

def findsubsets(S,m):
    ret = set()
    for i in range(2, m+1):
        ret |= set(itertools.combinations(S, i))

    return ret


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

def get_json(actual):
    target_fields = {}
    ret_data = robjects.r(actual)
    ret_type = robjects.r("sapply({df}, class)".format(df=actual))
    colnames = ret_data.colnames
    ret_json = robjects.r("toJSON({df})".format(df=actual))

    for i in range(0, len(ret_type)):
        t_obj = {}
        ret_t = ret_type[i]
        ret_d = ret_data[i]
        d_list = []
        for dt in ret_d:
            d_list.append(dt)

        if ret_t == 'numeric':
            t_obj["type"] = "number"
            t_obj["min"] = min(d_list)
            t_obj["max"] = max(d_list)
            t_obj["sum"] = sum(d_list)
        else:
            t_obj["type"] = "string"

        # print('*********', ret_d, type(ret_d), ret_t, type(ret_t))
        target_fields[colnames[i]] = t_obj

    json_wrapper = {}
    json_wrapper['values'] = json.loads(ret_json[0])
    # print('**********************\n', json_wrapper, "\n", target_fields)
    return (json_wrapper, target_fields)

# target_fields = {
#     "series": {"type": "string"},
#     "count": {"type": "integer"}
# }
def eq_r(actual, expect):
    ret_val = robjects.r(actual)
    # print(ret_val)
    ret_json = robjects.r("if(!anyNA({df}) && nrow({df}) > 1 && ncol({df}) > 1)  toJSON({df})"
        .format(df=actual))
    # print(ret_json)
    if ret_json:
        ret_data = robjects.r(actual)
        # print(ret_data)
        colnames = ret_data.colnames
        ncol = ret_data.ncol
        mid_list = list(range(1, ncol+1))
        blk_list = list(filter(lambda x: colnames[x-1]=='KEY' or colnames[x-1]=='VALUE', mid_list))
        all_set = findsubsets(list(range(1, ncol+1)), ncol)
        sub_set = list(filter(lambda x: all(elem in list(x) for elem in blk_list), all_set))
        if blk_list:
            # print(ncol, all_set, blk_list, 'my subset:', sub_set)
            for ele in sub_set:
                sel = 'c' + str(ele)
                sub_f = robjects.r("sub_f = select({df}, {se})".format(df=actual,se=sel))
                jj = get_json('sub_f')
                g_list.append(jj)

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

    def eval_group_by(self, node, args):
        n_cols = robjects.r('ncol(' + args[0] + ')')[0]
        self.assertArg(node, args,
                index=1,
                cond=lambda x: max(list(map(lambda y: int(y), x))) <= n_cols,
                capture_indices=[0])
        self.assertArg(node, args,
                index=1,
                       cond=lambda x: len(x) == 1,
                capture_indices=[0])

        ret_df_name = get_fresh_name()
        _script = '{ret_df} <- group_by({table}, {cols})'.format(
                   ret_df=ret_df_name, table=args[0], cols=get_collist(args[1]))
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except:
            logger.error('Error in interpreting group_by...')
            raise GeneralError()

    def eval_summarise(self, node, args):
        n_cols = robjects.r('ncol(' + args[0] + ')')[0]
        self.assertArg(node, args,
                index=2,
                cond=lambda x: x <= n_cols,
                capture_indices=[0])
        self.assertArg(node, args,
                index=2,
                cond=lambda x: get_type(args[0], str(x)) == 'integer' or get_type(args[0], str(x)) == 'numeric',
                capture_indices=[0])

        ret_df_name = get_fresh_name()
        _script = '{ret_df} <- {table} %>% summarise({TMP} = {aggr} (.[[{col}]]))'.format(
                  ret_df=ret_df_name, table=args[0], TMP=get_fresh_col(), aggr=str(args[1]), col=str(args[2]))
        try:
            ret_val = robjects.r(_script)
            return ret_df_name
        except:
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
                  ret_df=ret_df_name, table=args[0], TMP=get_fresh_col(), op=args[1], col1=str(args[2]), col2=str(args[3]))
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
        df = val
        if isinstance(val, str):
            df = robjects.r(val)
        ## df: rpy2.robjects.vectors.DataFrame

        return df.nrow

    def apply_col(self, val):
        df = val
        if isinstance(val, str):
            df = robjects.r(val)

        return df.ncol


def main():

    ##### Input-output constraint
    benchmark1_input = robjects.r('''
    dat <- read.table(text="
    round var1 var2 nam        val
    round1   22   33 foo 0.16912201
    round2   11   44 foo 0.18570826
    round1   22   33 bar 0.12410581
    round2   11   44 bar 0.03258235
    ", header=T)
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

    logger.info('Parsing Spec...')
    spec = None
    with open('dsl/morpheus.tyrell', 'r') as f:
        m_spec_str = f.read()
        spec = S.parse(m_spec_str)
    logger.info('Parsing succeeded')

    logger.info('Building synthesizer...')
    synthesizer = Synthesizer(
        spec=spec,
        #loc: # of function productions
        # enumerator=SmtEnumerator(spec, depth=2, loc=1),
        enumerator=SmtEnumerator(spec, depth=3, loc=2),
        # enumerator=SmtEnumerator(spec, depth=4, loc=3),
        interpreter=MorpheusInterpreter(),
        examples=[
            # Example(input=[DataFrame2(benchmark1_input)], output=benchmark1_output),
            Example(input=['dat'], output='dat2'),
        ],
        equal_output=eq_r
    )
    logger.info('Synthesizing programs...')

    prog = synthesizer.synthesize()
    if prog is not None:
        logger.info('Solution found: {}'.format(prog))
    else:
        logger.info('Solution not found!')

def get_sample_data(input_data):

    ##### Input-output constraint
    _iscript = "dat <- read.csv(file='{csv_file}')".format(csv_file=input_data)
    benchmark1_input = robjects.r(_iscript)

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
    return g_list


if __name__ == '__main__':
    logger.setLevel('DEBUG')
    main()
