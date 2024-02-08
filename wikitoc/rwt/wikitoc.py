"""A module to parse descriptions of wikibooks and facilitate
generating the wikitext pages for the book."""

__all__ = ['parse_file', 'parse_string', 'generate_nav_page']

import xml.etree.ElementTree as ET
import re

_brackets_re = re.compile(r'[][]')
_in_brackets_re = re.compile(r'\[(.*?)\]')
def _split_long_short(text):
    """Remove any brackets in `text`, and use the words inside the brackets as
    the short version of the string.  If there were no brackets, the short and
    long versions are the same."""
    if (m := _in_brackets_re.search(text)):
        return (_brackets_re.sub('',text), m.group(1))
    return (text, text)

class _WikiPage:
    _listmarks_re = re.compile(r'^[*#]++\s*+')
    _starts_an_the_re = re.compile(r'^(?:An?|The)\s*+', re.I)
    def __init__(self, parens, display, short=None, page=None):
        """build a page description from the display text, the
        optional short and page names, and the parenthetical that
        goes on the page name"""

        # Record and listmarks on the display, or default to '* '
        if (m := _WikiPage._listmarks_re.match(display)):
            self._listmarks = m.group(0)
            display = display[m.end():]
        else:
            self._listmarks = '* '

        # The short name is limited to 20 chars... if it's not given, we check for a bracketed section
        # of the display line
        if not short:
            display, short = _split_long_short(display)
            # now, try to whittle the short name to 20 chars...
            if len(short) > 20:
                short = _WikiPage._starts_an_the_re.sub('',short)
                if len(short) > 20:
                   short = f'{short[:18]}&hellip;'
        self._short, self._display = short, display

        # The page name, unless one is given, is the display name
        page = page or self._display
        # The link is the page name plus any given parenthetical
        if parens:
            self._link = f'{page} ({parens})'
        else:
            self._link = page

    def make_display_link(self):
        return f'{self._listmarks}[[{self._link}|{self._display}]]' 

    def make_short_link(self):
        return f'[[{self._link}|{self._short}]]' 

    def make_page_link(self,text=None):
        text = text or self._display
        return f'[[{self._link}|{text}]]' 

    def make_basic_link(self):
        """Make a link with no custom text"""
        return f'[[{self._link}]]' 

    def filename(self):
        """Generate a filename if we write this to disk"""
        return self._link.replace(' ','_') + '.wikitext'

# to make a category page:
#   WikiPage('Author', 'Table of [Contents]', page=':Category:Name of Book')
def _make_category_page(author, cat_page):
    """Create a WikiPage for the book category"""
    return _WikiPage(author, 'Table of [Contents]', page=f':Category:{cat_page}')

class _WikiBook:
    def __init__(self, author: (str, str), title: (str,str), toc_page:str, date: str):
        # (str,str) == (display, short)
        self._author, self._title, self._date = author, title, date
        self._toc_page = _make_category_page(author[1], toc_page) 
        self._category_mark = '[[' + self._toc_page.make_basic_link()[3:]
        self._nav = 'Generic WikiBook Nav'
        self._pages = []
        self._toc_text = []

    def add_page(self, display, short=None, page=None):
        wp = _WikiPage(self._title[1], display, short, page)
        self._toc_text.append(wp.make_display_link())
        self._pages.append(wp)

    def add_raw_text(self, text: str):
        self._toc_text.append(text)

    def generate_toc(self):
        return f"""; Title: {self._title[0]}
; Author: {self._author[0]}
; Date: {self._date}

[[File:{self._title[1].replace(' ','_')}_CoverImage.jpg|thumb|Cover Image]]
== Contents ==
{"\n".join(self._toc_text)}

[[Category:WikiBooks]]"""

    def page_or_toc(self, n):
        """Either find the page, or give the toc page if the number is out of range"""
        if n < 0 or n >= len(self._pages):
            return self._toc_page
        return self._pages[n]

    def __len__(self): return len(self._pages)

    def generate_page_template(self, n):
        """Generate a page wrapper for page number `n`"""
        prv, nxt = self.page_or_toc(n-1), self.page_or_toc(n+1)
        return f"""{{{{{self._nav}
| 1 = {self._title[0]}
| 2 = {self._toc_page.make_page_link()}
| 3 = {prv.make_short_link()}
| 4 = {nxt.make_short_link()}
}}}}

&rarr; {nxt.make_page_link()} &rarr;
{self._category_mark}"""

def generate_nav_page():
    """args: 1 = Title, 2 = ToC Link, 3 = prev link, 4 = next link"""
    return '''Nav page is Template:Generic_WikiBook_Nav

{| class="infobox wikitable floatright"
|-
! scope="colgroup" colspan="2" | {{{1}}}
|-
| style="text-align:center" colspan="2" | {{{2}}}
|-
| style="text-align:left" | &larr;&nbsp;{{{3}}}
| style="text-align:right" | {{{4}}}&nbsp;&rarr;
|}
'''

def _get_disp_short_page(element):
    """Get the display, short, and page fromt an element"""
    if element is None: return ('Unknown!', 'Unknown!', 'Unknown!')
    disp = element.text
    short = element.attrib.get('short',None)
    page = element.attrib.get('page',None)
    return (disp,short,page)

def _parse_disp_short_page(element):
    """Get the display, short, and page... providing defaults if short or page are None"""
    d,s,p = _get_disp_short_page(element)
    if s is None:
        d, s = _split_long_short(d)
    if p is None:
        p = d
    return (d,s,p)

def _parse(root):
    if root.tag != 'book': raise RuntimeError(f"Bad root <{root.tag}>! Should be <book>")

    # dig out the author, title, date, and create the _WikiBook
    tag_value = _parse_disp_short_page(root.find('author'))
    author = (tag_value[0], tag_value[1]) 
    tag_value = _parse_disp_short_page(root.find('title'))
    title = (tag_value[0], tag_value[1]) 
    book_page = tag_value[2]
    tag_value = _get_disp_short_page(root.find('date'))
    date = tag_value[0]
    wb = _WikiBook(author, title, book_page, date)

    # now go through the chapters...
    chapters = root.find('chapters')
    if chapters is None: raise RuntimeError("Book with no chapters!")
    for child in chapters:
        match child.tag:
            case 'c':
                dsp = _get_disp_short_page(child)
                wb.add_page(*dsp)
            case 'raw': 
                wb.add_raw_text(child.text)
            case unknown:
                raise RuntimeError(f"Chapter with tag <{unknown}>! Must be <c> or <raw>!")

    return wb

def parse_file(fname: str) -> _WikiBook:
    """Read a wikitoc xml file, and return the WikiBook"""
    tree = ET.parse(fname) 
    root = tree.getroot()
    return _parse(root)

def parse_string(s: str) -> _WikiBook:
    """Read a wikitoc xml string, and return the WikiBook"""
    root = ET.fromstring(s)
    return _parse(root)

