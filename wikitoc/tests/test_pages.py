# Run from the directory with pypackage.toml as:
#   python3 -m unittest discover -s tests

import unittest
from rwt import wikitoc as wt

class Test1(unittest.TestCase):
    def test_books_and_pages(self):
        b = wt.Book("Furthest Places, The (M. Rosas)","Love Novels");
        b.short_title = "Furthest Places";
        p1 = wt.Page(b,f"First Chapter, The ({b.short_title})")
        p1.display_name, p1.short_name = "The First Chapter", "First Chap."
        p2 = wt.Page(b,f"Second Chapter, The ({b.short_title})")
        p2.display_name, p2.short_name = "The Second Chapter", "Second Chap."
        
        b.add_page(p1)
        b.add_page(p2)
        self.assertIsNone(p1.prev_page)
        self.assertIsNone(p2.next_page)
        self.assertIs(p2,p1.next_page)
        self.assertIs(p1,p2.prev_page)
        self.assertEqual("[[First Chapter, The (Furthest Places)|First Chap.]]", p1.make_short_link())
        self.assertEqual("[[Second Chapter, The (Furthest Places)]]", p2.make_link())
        self.assertEqual("[[Second Chapter, The (Furthest Places)|The Second Chapter]]", p2.make_display_link())
        self.assertEqual("* [[Second Chapter, The (Furthest Places)|The Second Chapter]]", p2.make_toc_string())
        self.assertEqual("[[Category:Furthest Places, The (M. Rosas)]]", b.book_category_mark)
        self.assertEqual("[[Category:Love Novels]]", b.TOC.parent_category.make_category_marker())
