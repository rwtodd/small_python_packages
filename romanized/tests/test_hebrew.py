# Run from the directory with pypackage.toml as:
#   python3 -m unittest discover test

import unittest
from rwt.romanized import hebrew

class TestHebrew(unittest.TestCase):
    def test_abg(self):
        result = hebrew('A')
        self.assertEqual(result, "\u05d0")
        result = hebrew('B')
        self.assertEqual(result, "\u05d1")
        result = hebrew('G')
        self.assertEqual(result, "\u05d2")
        result = hebrew('ABG')
        self.assertEqual(result, 'אבג')

    def test_auto_finals(self):
        result = hebrew('AN BNM')
        self.assertEqual(result, 'אן בנם')
        result = hebrew('ANf BNiMf')
        self.assertEqual(result, 'אן בנם') 

    def test_niqqud(self):
        result = hebrew('B3AM')
        self.assertEqual(result, "\u05d1\u05b6\u05d0\u05dd")
        result = hebrew('B3*AMi*;3')
        self.assertEqual(result, "\u05d1\u05b6\u05bc\u05d0\u05de\u05bc\u05b1") 

    def test_sephirot(self):
        result = hebrew('KThR')
        self.assertEqual(result, 'כתר')
        result = hebrew('ChKMH')
        self.assertEqual(result, 'חכמה')
        result = hebrew('BINH')
        self.assertEqual(result, 'בינה')
        result = hebrew('DOTh')
        self.assertEqual(result, 'דעת')
        result = hebrew('ChSD')
        self.assertEqual(result, 'חסד')
        result = hebrew('GBVRH')
        self.assertEqual(result, 'גבורה')
        result = hebrew('ThPARTh')
        self.assertEqual(result, 'תפארת')
        result = hebrew('NTzCh')
        self.assertEqual(result, 'נצח')
        result = hebrew('HVD')
        self.assertEqual(result, 'הוד')
        result = hebrew('ISVD')
        self.assertEqual(result, 'יסוד')
        result = hebrew('MLKVTh')
        self.assertEqual(result, 'מלכות')

