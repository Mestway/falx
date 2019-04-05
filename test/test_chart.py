import unittest
from falx import chart

class TestChart(unittest.TestCase):

    def test_gen_chart(self):
        self.assertEqual('foo'.upper(), 'FOO')

if __name__ == '__main__':
    unittest.main()