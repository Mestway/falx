from namedlist import namedlist
from pprint import pprint

# mutatable vtrace
BarV = namedlist("BarV", ["x", "y1", "y2", "color", "column"], default=None)
BarH = namedlist("BarH", ["x1", "x2", "y", "color", "column"], default=None)
Point = namedlist("Point", ["shape", "x", "y", "size", "color", "column"], default=None)
Line = namedlist("Line", ["x1", "y1", "x2", "y2", "size", "color", "column"], default=None)
Area = namedlist("Area", ["x1", "yt1", "yb1", "x2", "yt2", "yb2", "color", "column"], default=None)
Box = namedlist("Box", ["x", "min", "max", "Q1", "median", "Q3", "color", "column"], default=None)

def get_vt_type(v):
    return type(v).__name__

def partition_trace(vtrace):
    """partition a trace based on its types """
    partition = {}
    for v in vtrace:
        vty = get_vt_type(v)
        if vty not in partition:
            partition[vty] = []
        partition[vty].append(v)
    return partition

def trace_contain(tr1, tr2):
    """check whether tr1 is contained by tr2 """
    pass

def trace_to_table(vtrace):
    trace_dict = partition_trace(vtrace)
    for ty in trace_dict:
        table = []
        for v in trace_dict[ty]:
            table.append(dict(v._asdict()))
        to_del = []
        for key in table[0].keys():
            if all([r[key] == None for r in table]):
                to_del.append(key)
        for r in table:
            for key in to_del:
                r.pop(key)
        trace_dict[ty] = table
    return trace_dict