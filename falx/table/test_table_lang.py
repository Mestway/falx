import unittest

from falx.table.language import *
import os

test_data = [{"Totals":7,"Value":"A","variable":"alpha","value":2,"cumsum":2},
             {"Totals":8,"Value":"B","variable":"alpha","value":2,"cumsum":2},
             {"Totals":9,"Value":"C","variable":"alpha","value":3,"cumsum":3},
             {"Totals":9,"Value":"D","variable":"alpha","value":3,"cumsum":3},
             {"Totals":9,"Value":"E","variable":"alpha","value":4,"cumsum":4},
             {"Totals":7,"Value":"A","variable":"beta","value":2,"cumsum":4},
             {"Totals":8,"Value":"B","variable":"beta","value":3,"cumsum":5},
             {"Totals":9,"Value":"C","variable":"beta","value":3,"cumsum":6},
             {"Totals":9,"Value":"D","variable":"beta","value":4,"cumsum":7},
             {"Totals":9,"Value":"E","variable":"beta","value":3,"cumsum":7},
             {"Totals":7,"Value":"A","variable":"gamma","value":3,"cumsum":7},
             {"Totals":8,"Value":"B","variable":"gamma","value":3,"cumsum":8},
             {"Totals":9,"Value":"C","variable":"gamma","value":3,"cumsum":9},
             {"Totals":9,"Value":"D","variable":"gamma","value":2,"cumsum":9},
             {"Totals":9,"Value":"E","variable":"gamma","value":2,"cumsum":9}]

table_data_2 = [{"Year":1961,"Drought":0,"Earthquake":60,"Epidemic":0,"Extreme temperature":400,"Flood":3863},{"Year":1962,"Drought":0,"Earthquake":12209,"Epidemic":0,"Extreme temperature":50,"Flood":1180},{"Year":1963,"Drought":0,"Earthquake":1700,"Epidemic":1000,"Extreme temperature":162,"Flood":1031},{"Year":1964,"Drought":50,"Earthquake":335,"Epidemic":617,"Extreme temperature":0,"Flood":1123},{"Year":1965,"Drought":1502000,"Earthquake":683,"Epidemic":816,"Extreme temperature":100,"Flood":1401},{"Year":1966,"Drought":8000,"Earthquake":2752,"Epidemic":200,"Extreme temperature":262,"Flood":1923},{"Year":1967,"Drought":600,"Earthquake":1013,"Epidemic":3137,"Extreme temperature":0,"Flood":2446},{"Year":1968,"Drought":0,"Earthquake":10858,"Epidemic":177,"Extreme temperature":153,"Flood":7306},{"Year":1969,"Drought":0,"Earthquake":3353,"Epidemic":3520,"Extreme temperature":0,"Flood":1544},{"Year":1970,"Drought":0,"Earthquake":78599,"Epidemic":939,"Extreme temperature":0,"Flood":3246},{"Year":1971,"Drought":0,"Earthquake":1107,"Epidemic":2313,"Extreme temperature":400,"Flood":2404},{"Year":1972,"Drought":0,"Earthquake":15170,"Epidemic":35,"Extreme temperature":110,"Flood":2548},{"Year":1973,"Drought":100000,"Earthquake":552,"Epidemic":0,"Extreme temperature":283,"Flood":1835},{"Year":1974,"Drought":19000,"Earthquake":24808,"Epidemic":1500,"Extreme temperature":0,"Flood":29431},{"Year":1975,"Drought":0,"Earthquake":12632,"Epidemic":0,"Extreme temperature":140,"Flood":848},{"Year":1976,"Drought":0,"Earthquake":276994,"Epidemic":396,"Extreme temperature":0,"Flood":960},{"Year":1977,"Drought":0,"Earthquake":3098,"Epidemic":1184,"Extreme temperature":0,"Flood":2568},{"Year":1978,"Drought":63,"Earthquake":25162,"Epidemic":3060,"Extreme temperature":150,"Flood":5897},{"Year":1979,"Drought":18,"Earthquake":2100,"Epidemic":486,"Extreme temperature":470,"Flood":1038},{"Year":1980,"Drought":0,"Earthquake":7730,"Epidemic":1685,"Extreme temperature":1389,"Flood":10466},{"Year":1981,"Drought":103000,"Earthquake":4206,"Epidemic":2497,"Extreme temperature":300,"Flood":5283},{"Year":1982,"Drought":280,"Earthquake":2120,"Epidemic":2912,"Extreme temperature":400,"Flood":4648},{"Year":1983,"Drought":450520,"Earthquake":2148,"Epidemic":1219,"Extreme temperature":205,"Flood":2082},{"Year":1984,"Drought":230,"Earthquake":57,"Epidemic":7016,"Extreme temperature":290,"Flood":2930},{"Year":1985,"Drought":0,"Earthquake":9853,"Epidemic":5854,"Extreme temperature":456,"Flood":4376},{"Year":1986,"Drought":84,"Earthquake":1181,"Epidemic":3046,"Extreme temperature":50,"Flood":1782},{"Year":1987,"Drought":1317,"Earthquake":5160,"Epidemic":2592,"Extreme temperature":1220,"Flood":6766},{"Year":1988,"Drought":1600,"Earthquake":27049,"Epidemic":15216,"Extreme temperature":644,"Flood":8504},{"Year":1989,"Drought":237,"Earthquake":650,"Epidemic":1870,"Extreme temperature":381,"Flood":4716},{"Year":1990,"Drought":0,"Earthquake":42853,"Epidemic":2207,"Extreme temperature":979,"Flood":2251},{"Year":1991,"Drought":2000,"Earthquake":2454,"Epidemic":30682,"Extreme temperature":835,"Flood":5852},{"Year":1992,"Drought":0,"Earthquake":4033,"Epidemic":6675,"Extreme temperature":388,"Flood":5315},{"Year":1993,"Drought":0,"Earthquake":10088,"Epidemic":651,"Extreme temperature":106,"Flood":6150},{"Year":1994,"Drought":0,"Earthquake":1242,"Epidemic":2505,"Extreme temperature":341,"Flood":6771},{"Year":1995,"Drought":0,"Earthquake":7739,"Epidemic":4428,"Extreme temperature":1730,"Flood":7956},{"Year":1996,"Drought":0,"Earthquake":576,"Epidemic":16887,"Extreme temperature":300,"Flood":8047},{"Year":1997,"Drought":732,"Earthquake":3159,"Epidemic":10674,"Extreme temperature":604,"Flood":7685},{"Year":1998,"Drought":20,"Earthquake":9573,"Epidemic":12931,"Extreme temperature":3269,"Flood":10653},{"Year":1999,"Drought":361,"Earthquake":21869,"Epidemic":6293,"Extreme temperature":771,"Flood":34807},{"Year":2000,"Drought":80,"Earthquake":217,"Epidemic":6980,"Extreme temperature":941,"Flood":6025},{"Year":2001,"Drought":99,"Earthquake":21348,"Epidemic":8515,"Extreme temperature":1787,"Flood":5014},{"Year":2002,"Drought":588,"Earthquake":1639,"Epidemic":8762,"Extreme temperature":3369,"Flood":4236},{"Year":2003,"Drought":9,"Earthquake":29617,"Epidemic":3522,"Extreme temperature":74698,"Flood":3910},{"Year":2004,"Drought":80,"Earthquake":227290,"Epidemic":3245,"Extreme temperature":255,"Flood":6982},{"Year":2005,"Drought":149,"Earthquake":76241,"Epidemic":3909,"Extreme temperature":1550,"Flood":5754},{"Year":2006,"Drought":134,"Earthquake":6692,"Epidemic":6402,"Extreme temperature":4826,"Flood":5843},{"Year":2007,"Drought":0,"Earthquake":780,"Epidemic":5484,"Extreme temperature":1086,"Flood":8607},{"Year":2008,"Drought":8,"Earthquake":87918,"Epidemic":6904,"Extreme temperature":1688,"Flood":4007},{"Year":2009,"Drought":0,"Earthquake":1893,"Epidemic":4895,"Extreme temperature":1386,"Flood":3627},{"Year":2010,"Drought":20000,"Earthquake":226733,"Epidemic":12143,"Extreme temperature":57188,"Flood":8356},{"Year":2011,"Drought":0,"Earthquake":20946,"Epidemic":3174,"Extreme temperature":435,"Flood":6163},{"Year":2012,"Drought":0,"Earthquake":711,"Epidemic":1887,"Extreme temperature":1834,"Flood":3544},{"Year":2013,"Drought":0,"Earthquake":1120,"Epidemic":529,"Extreme temperature":1821,"Flood":9836},{"Year":2014,"Drought":0,"Earthquake":774,"Epidemic":12911,"Extreme temperature":1168,"Flood":3532},{"Year":2015,"Drought":35,"Earthquake":9550,"Epidemic":1032,"Extreme temperature":7425,"Flood":3495},{"Year":2016,"Drought":0,"Earthquake":1311,"Epidemic":1520,"Extreme temperature":490,"Flood":4720},{"Year":2017,"Drought":0,"Earthquake":49,"Epidemic":386,"Extreme temperature":130,"Flood":648}]

inputs = {0: pd.DataFrame.from_dict(test_data)}

class TestTableLang(unittest.TestCase):
    
    def test_select(self):
        q = Table(data_id=0)
        q = Select(q, HOLE)
        print("---")
        print(q.stmt_string())
        print(q.is_abstract())
        print(q.eval(inputs=inputs) if not q.is_abstract() else "[Expression is abstract]")

    def test_group(self):
        q = Table(data_id=0)
        q = GroupSummary(q, [1], -1, "mean")
        print("---")
        print(q.stmt_string())
        print(q.is_abstract())
        #print(q.eval(inputs=inputs) if not q.is_abstract() else "[Expression is abstract]")

    def test_unite(self):
        q = Table(data_id=0)
        q = Unite(q, 1, 2)
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_filter(self):
        q = Table(data_id=0)
        q = Filter(q, 0, "==", 7)
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_separate(self):
        q = Table(data_id=0)
        q = Filter(q, 0, "==", 7)
        q = Unite(q, 1, 2)
        q = Separate(q, 3)
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_spread(self):
        q = Table(data_id=0)
        q = Select(q, [1, 2, 3])
        q = Spread(q, 1, 2)
        t = q.eval(inputs=inputs).reset_index()
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_gather(self):
        q = Table(data_id=0)
        q = Select(q, [1, 2, 3])
        q = Spread(q, 1, 2)
        q = Gather(q, [1, 2])
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs) if not q.is_abstract() else "[Expression is abstract]")

    def test_gather_neg(self):
        q = Table(data_id=0)
        q = Select(q, [1, 2, 3])
        q = Spread(q, 1, 2)
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_cumsum(self):
        q = Table(data_id=0)
        q = Select(q, [1, 2, 3])
        q = Filter(q, 1, "==", "alpha")
        q = CumSum(q, 3)
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_mutate(self):
        q = Table(data_id=0)
        q = Select(q, [1, 2, 3])
        q = Filter(q, 1, "==", "alpha")
        q = CumSum(q, 3)
        q = Mutate(q, 4, "-", 3)
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_mutate_custom(self):
        q = Table(data_id=0)
        q = Select(q, [1, 2, 3])
        q = MutateCustom(q, 1, "==", "alpha")
        print("---")
        print(q.stmt_string())
        #print(q.eval(inputs=inputs))

    def test_mutate_custom2(self):
        q = Table(data_id=0)
        q = Gather(q, [0, 1, 2, 3, 4])
        q = GroupSummary(q, [0], -1, "sum")
        print("---")
        print(q.stmt_string())
        print(q.eval(inputs={0: pd.DataFrame.from_dict(table_data_2)}))

if __name__ == '__main__':
    unittest.main()