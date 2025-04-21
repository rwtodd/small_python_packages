# a file for handling the "standard" wikitoc XML input file.

import xml.etree.ElementTree as _ET
import re as _re
from . import book as _wb

__all__ = [ 'TEMPLATE', 'parse_xml' ]

TEMPLATE = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<book tocCategory="??? WikiBooks">
  <!-- the table of contents will be a page named via <title> below, in category 'tocCategory'-->
  <!-- tocCategory will usually end in ' WikiBooks'-->
  <author>???</author>
  <title navtitle="???" short="???" url="???">???</title>
  <date>???</date>
  <chapters navtemplate="Generic WikiBook Nav">
    <!-- each chapter page will be in a category named after <title> and use a navigation template named by 'navtemplate' -->
    <raw>???</raw>
    <c short="???" url="???">???</c>
  </chapters>
</book>'''

_in_brackets_re = _re.compile(r'\[(.*?)\]')
_listmarks_re = _re.compile(r'^\s*+[*#]++\s*+')

def _split_list_marks(s: str) -> tuple[str|None,str]:
    if match := _listmarks_re.match(s):
        lm = match.group(0).strip() + ' '
        rest = s[match.end():]
        return (lm,rest)
    else:
        return (None, s)

def _parse(root: _ET.Element) -> _wb.Book:
    if root.tag != 'book': raise RuntimeError(f"Bad root <{root.tag}>! Should be <book>")
    known_attrs = set(['url','short'])
    toc_cat = root.get('tocCategory','Wikibooks')
    title_element = root.find('title')
    url = title_element.get('url',title_element.text)
    wb = _wb.Book(url, toc_cat)

    wb.title = title_element.text
    tmp = title_element.get('short')
    if tmp: wb.short_title = tmp
    tmp = title_element.get('navtitle')
    if tmp: wb.nav_title = tmp

    tmp = root.find('date')
    if tmp is not None: wb.pub_date = tmp.text
    
    tmp = root.find('author')
    if tmp is not None: wb.author = tmp.text

    chapters = root.find('chapters')
    if chapters is None: raise RuntimeError("Book with no chapters!")
    for child in chapters:
        match child.tag:
            case 'c':
                pgurl = child.get('url')
                pglistmark, pgtext = _split_list_marks(child.text)
                pgshort = child.get('short')
                # if there was no short page, check for brackets
                if not pgshort:
                    if match := _in_brackets_re.search(pgtext):
                        pgshort = match.group(1)
                        pgtext = f'{pgtext[:match.start()]}{pgshort}{pgtext[match.end():]}'
                # if there was no url, it must be the pgtext
                if not pgurl:
                    pgurl = pgtext
                # add the book's short title as a suffix to the url...
                pgurl = f"{pgurl} ({wb.short_title})"
                pg = _wb.Page(wb, pgurl)
                if pgshort: pg.short_name = pgshort
                if pgtext: pg.display_name = pgtext
                if pglistmark: pg.toc_listmarkers = pglistmark
                # if there are any attributes we don't know, add them as extra data...
                for k in (child.attrib.keys() - known_attrs):
                    pg.attributes[k] = (child.get(k) or "NO DATA")
                wb.add_page(pg)
            case 'raw': 
                wb.add_raw_text(child.text)
            case unknown:
                raise RuntimeError(f"Chapter with tag <{unknown}>! Must be <c> or <raw>!")
    return wb

def parse_xml(infile : str) -> _wb.Book:
    """Read a wikitoc xml file, and return the wikitoc.book.Book"""
    tree = _ET.parse(infile) 
    root = tree.getroot()
    return _parse(root)
