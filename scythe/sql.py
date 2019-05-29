import json
import os

class SQL(object):
    def __init__(self):
        pass

    def is_abstract(self):
        return False

    def get_schema(self):
        raise NotImplementedError

    def get_qualified_fields(self):
        name, fields = self.get_schema()
        return ["{}.{}".format(name, f) for f in fields]

class Table(SQL):
    def __init__(self, name, fields, values):
        self.name = name
        self.fields = fields
        self.values = values

    def get_schema(self):
        return (self.name, self.fields)

    def eval(self):
        return self.values

class Select(SQL):
    def __init__(self, q, cols, pred):
        self.cols = cols
        self.q = q
        self.pred = pred

    def eval(self):
        table = self.q.eval()
        schema = self.q.get_qualified_fields()
        res = []
        for r in table:
            binding = {s:r[i] for i, s in enumerate(schema)}
            if self.pred.eval(binding):
                res.append([cv.eval(binding) for cv in self.cols])
        return res

class Join(SQL):
    def __init__(self, q1, q2, pred):
        self.q1 = q1
        self.q2 = q2
        self.pred = pred

    def eval(self):
        schema1, t1 = self.q1.get_qualified_fields(), self.q1.eval()
        schema2, t2 = self.q2.get_qualified_fields(), self.q2.eval()
        res = []
        for r1 in t1:
            b1 = {s:r1[i] for i, s in enumerate(schema1)}
            for r2 in t2:
                b2 = {s:r2[i] for i, s in enumerate(schema2)}
                # merge two dicts
                if self.pred.eval({**b1, **b2}):
                    res.append(r1 + r2)
        return res

class Aggr(SQL):
    def __init__(self, q, gb_fields, targets, having_pred):
        """group_fields is a list of columns
            targets is a list of (aggr_function, columns, new_name) tuples
        """
        self.q = q
        self.gb_fields = gb_fields
        self.targets = targets
        self.having_pred = having_pred

    def eval(self):
        schema, table = self.q.get_qualified_fields(), self.q.eval()
        groups = {}
        for r in table:
            binding = {s:r[i] for i, s in enumerate(schema)}
            gb_vals = tuple([f.eval(binding) for f in self.gb_fields])
            if gb_vals not in groups:
                groups[gb_vals] = []
            groups[gb_vals].append(r)

        res = []
        for gb_vals in groups:
            aggr_vals = []
            for aggr_func, target_col, _ in self.targets:
                vals = [target_col.eval({s:r[i] for i, s in enumerate(schema)}) for r in groups[gb_vals]]
                aggr_vals.append(aggr_func(vals))
            
            gb_binding = {s:gb_vals[i] for i, s in enumerate(self.gb_fields)}
            aggr_binding = {s[2]:aggr_vals[i] for i, s in enumerate(self.targets)}

            # merge two dicts and eval having pred
            if self.having_pred.eval({**gb_binding, **aggr_binding}):
                res.append(list(gb_vals) + aggr_vals)
        return res

class Union(SQL):
    def __init__(self, q1, q2):
        self.q1 = q1
        self.q2 = q2

    def eval(self):
        return self.q1.eval() + self.q2.eval()

class LeftJoin(SQL):
    def __init__(self, q1, q2, pred):
        self.q1 = q1
        self.q2 = q2
        self.pred = pred

    def eval(self):
        schema1, t1 = self.q1.get_qualified_fields(), self.q1.eval()
        schema2, t2 = self.q2.get_qualified_fields(), self.q2.eval()

        res = []
        for r1 in t1:
            b1 = {s:r1[i] for i, s in enumerate(schema1)}
            r1_used = False
            for r2 in t2:
                b2 = {s:r2[i] for i, s in enumerate(schema2)}
                # merge two dicts
                if self.pred.eval({**b1, **b2}):
                    res.append(r1 + r2)
                    r1_used = True
            if not r1_used:
                # if there is no matching column, add it with null fields
                res.append(r1 + [None for i in range(len(schema2))])
        return res

class As(SQL):
    def __init__(self, q, name, fields):
        self.q = q
        self.name = name
        self.fields = fields

    def get_schema(self):
        return (self.name, self.fields)

    def eval(self):
        return self.q.eval()

class ConjPred(object):
    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2

    def eval(self, binding):
        return self.p1.eval(binding) and self.p2.eval(binding)

class DisjPred(object):
    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2

    def eval(self, binding):
        return self.p1.eval(binding) or self.p2.eval(binding)

class BasicPred(object):
    def __init__(self, op, v1, v2):
        self.op = op
        self.v1 = v1
        self.v2 = v2

    def eval(self, binding):
        return self.op(self.v1.eval(binding), self.v2.eval(binding))

class TruePred(object):
    def __init__(self):
        pass

    def eval(self, binding):
        return True

class IsNullPred(object):
    def __init__(self, c):
        self.c = c

    def eval(self, binding):
        return self.c.eval(binding) is None

class ConstVal(object):
    def __init__(self, v):
        self.v = v

    def eval(self, binding):
        return self.v

class ColRef(object):
    def __init__(self, c):
        self.c = c
    
    def eval(self, binding):
        return binding[self.c]