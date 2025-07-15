# module rwt.epub
# contains an epub-writing helper

from pathlib import Path
import zipfile as _zipfile
import uuid
import datetime

_CONTAINER_XML = """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
 <rootfiles>
  <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
 </rootfiles>
</container>"""

class EpubWriter:
    @staticmethod
    def media_type(fname:str) -> str:
        """Generate a media type from a file name"""
        if fname.endswith('webp'):
            return 'image/webp'
        elif fname.endswith('xhtml'):
            return 'application/xhtml+xml'
        else:
            return 'image/jpeg'    
    @staticmethod
    def img_path(fname: str, relative: bool = False) -> str:
        """Generate the zip path of an image"""
        if relative:
            return '../Images/' + fname
        else:
            return 'OEBPS/Images/' + fname
    @staticmethod
    def xhtml_path(fname: str, relative: bool = False) -> str:
        """Generate the zip path of an xhtml file"""
        if relative:
            return fname
        else:
            return 'OEBPS/Text/' + fname
    @staticmethod
    def content_path() -> str:
        """Generate the filename for the content.opf file"""
        return 'OEBPS/content.opf'

    def __init__(self, fname: str, title: str, author: str, pubyear: int):
        """Create an EPUB file, and prepare to fill it with contents"""
        self._title, self._author, self._pubyear = title, author, pubyear
        self._coverfile = None
        self._img_dims : dict[str,tuple[int,int]] = dict()
        self._contents : list[dict[str,str]] = list() # all the files we've added: keys {fname,zip_path,media_type,properties}
        self._spine : list[str] = list() # the pages, in order
        self._toc_links : list[tuple[str,str]] = list() # list of [link, plain text] for the TOC
        self._zipfile : _zipfile.ZipFile = _zipfile.ZipFile(fname, 'w', compression=_zipfile.ZIP_DEFLATED, compresslevel = 9)
        self._zipfile.writestr('mimetype', 'application/epub+zip', _zipfile.ZIP_STORED)
        self._zipfile.writestr('META-INF/container.xml', _CONTAINER_XML)
            
    def __enter__(self):
        """Nothing todo when entering a context manager"""
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        """close the zip file if we haven't already, when leaving the context"""
        self.close()

    def close(self):
        """Close the zipfile, if not closed"""
        self._generate_nav_page()
        self._generate_content_opf()
        self._zipfile.close() # FIXME do I need to protect against double-close?

    def _generate_content_opf(self):
        """Create the content.opf file"""
        if self._coverfile is None:
            raise Exception('No cover file was set!')
        if len(self._spine) == 0:
            raise Exception('Spine is empty!')
        parts = []
        parts.append(f"""<?xml version="1.0" encoding="utf-8"?>
<package version="3.0" unique-identifier="BookId" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:language>en</dc:language>
    <dc:creator id="cre">{self._author}</dc:creator>
    <meta refines="#cre" property="role" scheme="marc:relators">aut</meta>
    <dc:date>{self._pubyear}</dc:date>
    <dc:title>{self._title}</dc:title>
    <meta property="dcterms:modified">{datetime.date.today().isoformat()}T12:00:00Z</meta>
    <dc:identifier id="BookId">urn:uuid:{uuid.uuid4()}</dc:identifier>
    <meta name="cover" content="{self._coverfile}" />
  </metadata>
  <manifest>""")
        for item in self._contents:
            propstr = '' if len(item['properties']) == 0 else f' properties="{item["properties"]}"'
            oebps_relative = item['zip_path'][6:]
            parts.append(f'<item id="{item["fname"]}" href="{oebps_relative}" media-type="{item["media_type"]}"{propstr}/>')
        parts.append(f""" </manifest>
  <spine>
    <itemref idref="{self._spine[0]}"/>
    <itemref idref="nav.xhtml" linear="no"/>
""")
        parts.append('\n'.join(f'<itemref idref="{pg}"/>' for pg in self._spine[1:]))
        parts.append(""" </spine>
</package>""")
        self._zipfile.writestr(self.content_path(), '\n'.join(parts))

    def _generate_nav_page(self):
        """Create a nav.xhtml file for the epub document"""
        parts = []
        parts.append(f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">
<head>
  <title>ePub NAV</title>
  <style>nav#landmarks {{ display:none; }}
nav#page-list {{ display:none; }}
ol {{ list-style-type: none; }}
</style>
</head>
<body epub:type="frontmatter">
  <nav epub:type="toc" id="toc" role="doc-toc">
    <h1>Table of Contents</h1>
    <ol>""")
        parts.extend(f'<li><a href="{self.xhtml_path(pg, relative=True)}">{txt}</a></li>' for (pg,txt) in self._toc_links)
        parts.append(f"""    </ol>
  </nav>
<nav epub:type="landmarks" id="landmarks" hidden="">
    <h1>Landmarks</h1>
    <ol>
      <li>
        <a epub:type="toc" href="#toc">Table of Contents</a>
      </li>
      <li>
        <a epub:type="cover" href="{self.xhtml_path(self._spine[0], relative=True)}">Cover</a>
      </li>
    </ol>
  </nav>
</body>
</html>""")
        xhtml_fname = 'nav.xhtml'
        zip_path = self.xhtml_path(xhtml_fname)
        self._zipfile.writestr(zip_path, '\n'.join(parts))
        self._contents.append({
            'fname': xhtml_fname, 
            'zip_path': zip_path, 
            'media_type': self.media_type(xhtml_fname), 
            'properties': 'nav'})

    def add_toc_link(self, referent: str, text: str):
        """Add a link in the nav page for `referent` with text `text`"""
        self._toc_links.append( (referent, text) )

    def add_image_content(self, img_fname:str, img_data: bytes, is_cover: bool = False, img_dims: tuple[int,int]|None = None):
        """Add an image as `img_fname` to the archive, with payload `img_data` and remember the
        dimensions of the image.  If you don't know the image dimensions"""
        if (self._coverfile is None) or is_cover:
            self._coverfile = img_fname
        if img_dims is not None:
            self._img_dims[img_fname] = img_dims
        props = 'cover-image' if is_cover else ''
        zip_path = self.img_path(img_fname)
        self._zipfile.writestr(zip_path, img_data)
        self._contents.append({
            'fname': img_fname, 
            'zip_path': zip_path, 
            'media_type': self.media_type(img_fname), 
            'properties': props})

    def add_fullpage_pic(self, xhtml_fname:str, img_fname:str):
        """Add a fullpage-svg image by the name `xhtml_fname`, for the image named `img_fname`"""
        try:
            w,h = self._img_dims[img_fname]
            content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>{Path(img_fname).stem}</title>
</head>
<body>
  <div style="height: 100vh; text-align: center; padding: 0pt; margin: 0pt;">
    <svg xmlns="http://www.w3.org/2000/svg" height="100%" preserveAspectRatio="xMidYMid meet" version="1.1" viewBox="0 0 {w} {h}" width="100%" xmlns:xlink="http://www.w3.org/1999/xlink">
      <image width="{w}" height="{h}" xlink:href="{self.img_path(img_fname, relative=True)}"/>
    </svg>
  </div>
</body>
</html>"""
            self.add_xhtml_content(xhtml_fname, content, 'svg')
        except KeyError:
            raise Exception(f"Don't have dimensions for the image {img_fname}!")
    
    def add_xhtml_content(self, xhtml_fname:str, xhtml_content:str, properties: str = ''):
        """Add an xhtml page to the epub with the given properties"""
        zip_path = self.xhtml_path(xhtml_fname)
        self._zipfile.writestr(zip_path, xhtml_content)
        self._contents.append({
            'fname': xhtml_fname, 
            'zip_path': zip_path, 
            'media_type': self.media_type(xhtml_fname), 
            'properties': properties})
        self._spine.append(xhtml_fname)
