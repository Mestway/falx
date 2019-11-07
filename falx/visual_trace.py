from namedlist import namedlist
from pprint import pprint

# mutatable vtrace
BarV = namedlist("BarV", ["x", "y1", "y2", "color", "column"], default=None)
BarH = namedlist("BarH", ["x1", "x2", "y", "color", "column"], default=None)
Point = namedlist("Point", ["point_shape", "shape", "x", "y", "size", "color", "column"], default=None)
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

def load_trace(raw_trace):
    """Given a trace represnted as a dictionary, 
        return the trace list built using the constructor
        Format: {"type": "trace_type", "props": {"x": ..., "y": ...}}"""

    def convert_one(trace_dict):
        get_prop = lambda k: None if (k not in trace_dict["props"] or trace_dict["props"][k] == "") else trace_dict["props"][k]

        if trace_dict["type"] == "bar":
            if get_prop("x2") != None:
                return BarH(x1=get_prop("x"), x2=get_prop("x2"), y=get_prop("y"), color=get_prop("color"), column=get_prop("column"))
            else:
                return BarV(x=get_prop("x"), y1=get_prop("y"), y2=get_prop("y2"), color=get_prop("color"), column=get_prop("column"))
        elif trace_dict["type"] in ["point", "rect"]:
            return Point(point_shape=trace_dict["type"], x=get_prop("x"), y=get_prop("y"), shape=get_prop("shape"), 
                         size=get_prop("size"), color=get_prop("color"), column=get_prop("column"))
        elif trace_dict["type"] == "line":
            return Line(x1=get_prop("x1"), y1=get_prop("y1"), x2=get_prop("x2"), y2=get_prop("y2"), 
                        size=get_prop("size"), color=get_prop("color"), column=get_prop("column"))
        else:
            return None
    return [convert_one(tr) for tr in raw_trace]


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