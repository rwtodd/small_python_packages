"""A module to parse descriptions of wikibooks and facilitate
generating the wikitext pages for the book."""

__all__ = ['Book', 'Page', 'generate_nav_page']

_UNK = "UNKNOWN"

class RawText:
    """Raw text for the TOC page, may be mixed freely with `Page`s."""
    def __init__(self, text: str):
        self.text = text
    def make_toc_string(self):
        return self.text

class Page:
    def __init__(self, book: 'Book', url: str):
        self._book = book
        self._url = url
        self._next_page = None
        self._prev_page = None
        self._short_name = None
        self._display_name = None
        self._is_category = None
        self._toc_listmarkers = None
        self._attributes = None

    @property
    def attributes(self) -> dict[str,str]:
        """Any extra data associtated with the page"""
        adict = self._attributes
        if adict is None:
            adict = dict()
            self._attributes = adict
        return adict

    @property
    def book(self) -> 'Book':
        return self._book
    
    @property
    def url(self) -> str:
        return self._url
    
    def _set_displayname(self, dn:str):
        self._display_name = dn
    def _get_displayname(self) -> str:
        return self._display_name or self._url
    display_name = property(_get_displayname, _set_displayname, None, "The 'display name' for the page.")

    def _set_next_page(self, pg: 'Page'):
        self._next_page = pg
    @property
    def next_page(self) -> 'Page':
        return self._next_page
    
    def _set_prev_page(self, pg: 'Page'):
        self._prev_page = pg
    @property
    def prev_page(self) -> 'Page':
        return self._prev_page

    def _set_short_name(self, sn: str):
        self._short_name = sn
    def _get_short_name(self) -> str:
        candidate = self._short_name or self.display_name
        if len(candidate) > 20:
            if candidate.startswith('A '):
                candidate = candidate[2:]
            elif candidate.startswith('An '):
                candidate = candidate[3:]
            elif candidate.startswith('The '):
                candidate = candidate[4:]
            if len(candidate) > 20:
                candidate = candidate[:18] + '&hellip;'
        return candidate
    short_name = property(_get_short_name,_set_short_name,None,"The 'short name' for this page")

    def _set_toc_listmarkers(self, lm: str):
        self._toc_listmarkers = lm
    def _get_toc_listmarkers(self) -> str:
        return self._toc_listmarkers or "* "
    toc_listmarkers = property(_get_toc_listmarkers, _set_toc_listmarkers, None, "The list markers that precede the page in the TOC listing")

    def _get_is_category(self) -> bool:
        return self._is_category or False
    def _set_is_category(self, ic: bool):
        self._is_category = ic
    is_category = property(_get_is_category, _set_is_category, None, "Is the page representing a category?")

    @property
    def file_name(self) -> str:
        return f"{self.url}.wikitext".replace(' ', '_')
    
    def make_link(self, text: str = None) -> str:
        """if text is None, then no link text is given in the link,
        and mediawiki will display the page name as the link text."""
        if text is None:
            ending = ''
        else:
            ending = f'|{text}'
        cat = ":Category:" if self.is_category else ''
        return f'[[{cat}{self.url}{ending}]]'

    def make_display_link(self) -> str:
        return self.make_link(self.display_name)
    
    def make_short_link(self) -> str:
        return self.make_link(self.short_name)
    
    def make_category_marker(self) -> str:
        if not self.is_category:
            raise RuntimeError('Category marker requested for non-category!')
        return f'[[Category:{self.url}]]'
    
    def make_toc_string(self) -> str:
        return f"{self.toc_listmarkers}{self.make_display_link()}"
    
    def _page_contents(self) -> str:
        """Get the contents of the page for the template. This is useful to override in child
        classes, but in the base Page class it returns an empty string."""
        return ""
    
    def _page_postscript(self) -> str:
        """Get any contents you want to place _after_ the default template.  This is useful to override
        in child classes, but in the base Page class it returns an empty string."""
        return ""
    
    def make_page_template(self) -> str:
        book = self.book
        contents = self._page_contents().strip()
        postlude = self._page_postscript().strip()
        return f"""{{{{{book.nav_template}
|1 = {book.nav_title}
|2 = {book.TOC.make_display_link()}
|3 = {(self.prev_page or book.TOC).make_short_link()}
|4 = {(self.next_page or book.TOC).make_short_link()}
}}}}
{contents}

&rarr; {(self.next_page or book.TOC).make_display_link()} &rarr;

{postlude}
{book.book_category_mark}"""

class TableOfContents(Page):
    def __init__(self, book: 'Book', url_name: str, parent_cat: str):
        super().__init__(book, url_name)
        self.short_name = "Contents"
        self.display_name = "Table of Contents"
        self.toc_listmarkers = ''
        pcat_page = Page(book, parent_cat)
        pcat_page.is_category = True
        self._set_parent_category(pcat_page)
        self._entries = []
    
    def _set_parent_category(self, cat: Page):
        self._parent_category = cat
    @property
    def parent_category(self) -> Page:
        return self._parent_category
    
    def make_page_template(self) -> str:
        book = self.book
        lines = []
        lines.append(f"; Title: {book.title}")
        lines.append(f"; Author: {book.author}")
        lines.append(f"; Date: {book.pub_date}")
        lines.append('')
        lines.append(f"[[File:{book.short_title} CoverImage.jpg|thumb|Cover Image]]".replace(' ','_'))
        lines.append("== Contents ==")
        lines.extend(e.make_toc_string() for e in self._entries)
        lines.append('')
        lines.append(self.parent_category.make_category_marker())
        return "\n".join(lines)
    
    def _add_entry(self, e) -> None:
        """e is anything that supports a make_toc_string() method"""
        self._entries.append(e)

class Book:
    def __init__(self, book_url: str, toc_cat: str):
        self._toc = TableOfContents(self, book_url, toc_cat)
        cmark = Page(self, book_url)
        cmark.is_category = True
        self._category_mark = cmark.make_category_marker()
        self._nav_template = None
        self._pages : list[Page] = []
        self._unique_urls = set([book_url])
        self._author = None
        self._pub_date = None
        self._title = None
        self._short_title = None
        self._nav_title = None
    @property
    def TOC(self) -> TableOfContents:
        return self._toc
    
    @property
    def book_category_mark(self) -> str:
        return self._category_mark

    def _set_nav_template(self, nt: str):
        self._nav_template = nt
    def _get_nav_template(self) -> str:
        return self._nav_template or 'Generic WikiBook Nav'
    nav_template = property(_get_nav_template,_set_nav_template,None,"The navigation template the book pages will use")
    
    def add_page(self, p: Page):
        if p.url in self._unique_urls:
            raise RuntimeError('Adding the same url page twice! ' + p.url)
        self._unique_urls.add(p.url)
        
        if len(self._pages) > 0:
            lastp = self._pages[-1]
            lastp._set_next_page(p)
            p._set_prev_page(lastp)        
        self._pages.append(p)
        self.TOC._add_entry(p)

    def add_raw_text(self, text: str):
        self.TOC._add_entry(RawText(text))
    
    @property
    def pages(self) -> list[Page]:
        return self._pages # TODO: does making a copy here make sense?
    
    def _set_pub_date(self, date: str):
        self._pub_date = date
    def _get_pub_date(self) -> str:
        return self._pub_date or _UNK
    pub_date = property(_get_pub_date, _set_pub_date, None, "The date of publication")

    def _set_title(self, title: str):
        self._title = title
    def _get_title(self) -> str:
        return self._title or _UNK
    title = property(_get_title, _set_title, None, "The title of the book")

    def _set_nav_title(self, nav_title: str):
        self._nav_title = nav_title
    def _get_nav_title(self) -> str:
        return self._nav_title or self.title
    nav_title = property(_get_nav_title, _set_nav_title, None, "The navigation-page title of the book")

    def _set_short_title(self, short_title: str):
        self._short_title = short_title
    def _get_short_title(self) -> str:
        return self._short_title or self.title
    short_title = property(_get_short_title, _set_short_title, None, "The short title of the book (often used in page urls)")

    def _set_author(self, author: str):
        self._author = author
    def _get_author(self) -> str:
        return self._author or _UNK
    author = property(_get_author, _set_author, None, "The author of the book")

def generate_nav_page() -> str:
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

