import os

def table_content_contain(t1, t2):
	""" check if t1 contains t2"""
	for r in t2:
		cnt_in_t2 = len([r for r2 in t2 if tuple(r2) == tuple(r)])
		cnt_in_t1 = len([r for r1 in t1 if tuple(r1) == tuple(r)])
		if cnt_in_t2 > cnt_in_t1:
			return False
	return True

def table_content_eq(t1, t2):
	return table_content_contain(t1, t2) and table_content_contain(t2, t1)