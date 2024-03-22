# testing english qabalah
# Run from the directory with pypackage.toml as:
#   python3 -m unittest discover -s tests
import unittest
from rwt.gematria import english as eq

class TestALW(unittest.TestCase):
    def test_love(self):
        alw = eq.Cipher('alw')
        self.assertEqual(46, alw.sum('one'))
        self.assertEqual(46, alw.sum('woman'))
        self.assertEqual(68, alw.sum('life'))
        self.assertEqual(68, alw.sum('Jesus'))

class TestSimple(unittest.TestCase):
    def test_simple(self):
        smp = eq.Cipher('simple')
        self.assertEqual(1,smp.sum('a'))
        self.assertEqual(26,smp.sum('Z'))
        self.assertEqual(10,smp.sum('abcd'))