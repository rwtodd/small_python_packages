# Run from the directory with pypackage.toml as:
#   python3 -m unittest discover -s tests

import unittest
from rwt.romanized import greek 

class TestGreek(unittest.TestCase):
    def test_abg(self):
        result = greek('A*A')
        self.assertEqual(result, "\u03b1\u0391")
        result = greek('B*B')
        self.assertEqual(result, "\u03b2\u0392")
        result = greek('G*G')
        self.assertEqual(result, "\u03b3\u0393")
        result = greek('ABG')
        self.assertEqual(result, 'αβγ')

    def test_auto_finals(self):
        result = greek('BAS SAS')
        self.assertEqual(result, 'βας σας')
        result = greek('BAS *S*A*S')
        self.assertEqual(result, 'βας ΣΑΣ')

    def test_accents(self):
        result = greek('*)B?A')
        self.assertEqual(result, "\u0392\u0313\u0323\u03b1")

