# Run from the directory with pypackage.toml as:
#   python3 -m unittest discover -s tests

import unittest
from rwt.discordian import DiscordianDate
from datetime import date

class Test1(unittest.TestCase):
    def test_basic_xday(self):
        for (day, remaining) in [(5, 0), (4, 1), (3, 2), (2, 3), (1, 4), (6,-1)]:
            d = DiscordianDate(date(8661,7,day))
            self.assertEqual(d.days_til_xday, remaining)

    def test_a_chaoflux(self):
        d = DiscordianDate(date(1956,2,19))
        self.assertTrue(d.is_holy_day)
        self.assertFalse(d.is_tibs)
        self.assertEqual(d.holy_day_name, "Chaoflux")
        self.assertEqual(d.days_til_xday, 2449088)
        self.assertEqual(d.weekday, "Setting Orange")
        self.assertEqual(d.short_weekday, "SO")
        self.assertEqual(d.season, "Chaos")
        self.assertEqual(d.short_season, "Chs")
        self.assertEqual(d.day_of_season, 50)
    
    def test_a_nonholy_day(self):
        d = DiscordianDate(date(1977,6,1))
        self.assertFalse(d.is_holy_day)
        self.assertFalse(d.is_tibs)
        self.assertEqual(d.holy_day_name, "")
        self.assertEqual(d.days_til_xday, 2441315)
        self.assertEqual(d.weekday, "Boomtime")
        self.assertEqual(d.short_weekday, "BT")
        self.assertEqual(d.season, "Confusion")
        self.assertEqual(d.short_season, "Cfn")
        self.assertEqual(d.day_of_season, 6)
    

