# rwt_epub
# A tiny, pure-Python EPUB 3 writer.
# Supports images (all EPUB core types), XHTML (raw or easy body-only wrapper),
# multiple CSS stylesheets (auto-linked from wrappers), full-page SVG images,
# and a clean 3-level TOC with targets by filename or 1-based chapter number.

from pathlib import Path as _Path
import zipfile as _zipfile
import uuid as _uuid
import datetime as _datetime
import importlib.resources as _resources
from collections import namedtuple as _namedtuple

_ContentItem = _namedtuple("_ContentItem", ["fname", "zip_path", "media_type", "properties"])
_TocEntry = _namedtuple("_TocEntry", ["level", "target", "text"])

_CONTAINER_XML = """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
 <rootfiles>
  <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
 </rootfiles>
</container>"""

# EPUB 3.3 core media types (relevant subset)
_MEDIA_TYPES: dict[str, str] = {
    # Images (all required for viewport reading systems)
    "gif": "image/gif",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "svg": "image/svg+xml",
    "webp": "image/webp",
    # Content documents
    "xhtml": "application/xhtml+xml",
    "html": "application/xhtml+xml",
    "htm": "application/xhtml+xml",
    # Styles
    "css": "text/css",
}

def _ensure_extension(name: str, ext: str) -> str:
    """If the name does not end with ext, add it"""
    if not name.lower().endswith(ext):
        return name + ext
    return name

def _ensure_epub_extension(name: str) -> str:
    return _ensure_extension(name, '.epub')

def _ensure_xhtml_extension(name: str) -> str:
    return _ensure_extension(name, '.xhtml')

def _ensure_css_extension(name: str) -> str:
    return _ensure_extension(name, '.css')

# --- Default cover image handling (real file shipped in the package) ---

_DEFAULT_COVER_RESOURCE = "default_cover.jpg"
# Known dimensions of the shipped default_cover.jpg (640x914 as of 2026-05)
_DEFAULT_COVER_DIMS: tuple[int, int] = (640, 914)


def _load_default_cover_bytes() -> bytes:
    """Load the packaged default cover JPEG using importlib.resources.

    This works whether the package is installed from wheel, sdist, or in
    editable/development mode.
    """
    return (
        _resources.files("rwt_epub") / _DEFAULT_COVER_RESOURCE
    ).read_bytes()


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    """Return (width, height) for a JPEG, or None if it cannot be determined.

    Pure-Python, no external dependencies. Only looks at the Start-Of-Frame
    markers that contain the image dimensions.
    """
    if len(data) < 2 or data[0:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 4 < len(data):
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):  # SOF0, SOF1, SOF2
            # Big-endian height, width at offset +5 and +7 inside the segment
            if i + 9 > len(data):
                return None
            height = int.from_bytes(data[i + 5 : i + 7], "big")
            width = int.from_bytes(data[i + 7 : i + 9], "big")
            return (width, height)
        # Skip to next marker
        if marker in (0xD8, 0xD9):  # SOI, EOI — no length
            i += 2
            continue
        if 0xD0 <= marker <= 0xD7:  # RSTn
            i += 2
            continue
        # All other markers have a 2-byte length field (big-endian)
        length = int.from_bytes(data[i + 2 : i + 4], "big")
        i += 2 + length
    return None


class EpubWriter:
    @staticmethod
    def media_type(fname: str) -> str:
        """Return the EPUB media type for a filename based on its extension."""
        ext = _Path(fname).suffix.lower().lstrip(".")
        return _MEDIA_TYPES.get(ext, "application/octet-stream")

    @staticmethod
    def img_path(fname: str, relative: bool = False) -> str:
        """Generate the zip path of an image."""
        if relative:
            return "../Images/" + fname
        return "OEBPS/Images/" + fname

    @staticmethod
    def xhtml_path(fname: str, relative: bool = False) -> str:
        """Generate the zip path of an XHTML (or other Text/) file."""
        if relative:
            return fname
        return "OEBPS/Text/" + fname

    @staticmethod
    def css_path(fname: str, relative: bool = False) -> str:
        """Generate the zip path of a CSS stylesheet."""
        if relative:
            return "../Styles/" + fname
        return "OEBPS/Styles/" + fname

    @staticmethod
    def content_path() -> str:
        """Generate the filename for the content.opf file."""
        return "OEBPS/content.opf"

    def __init__(self, fname: str, title: str, author: str, pubyear: int):
        """Create an EPUB file and prepare to fill it with contents."""
        self._title = title
        self._author = author
        self._pubyear = pubyear
        self._coverfile: str | None = None
        self._img_dims: dict[str, tuple[int, int]] = {}
        self._contents: list[_ContentItem] = []
        self._spine: list[str] = []
        self._toc_entries: list[_TocEntry] = []
        self._stylesheets: list[str] = []  # basenames, in the order added (for link order)
        self._zipfile = _zipfile.ZipFile(
            _ensure_epub_extension(fname), "w", compression=_zipfile.ZIP_DEFLATED, compresslevel=9
        )
        self._zipfile.writestr("mimetype", "application/epub+zip", _zipfile.ZIP_STORED)
        self._zipfile.writestr("META-INF/container.xml", _CONTAINER_XML)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

    def _ensure_cover(self):
        """If the user never supplied a cover image, inject the packaged default cover.

        The default is a real JPEG file shipped inside the rwt_epub package
        (leather texture with "BOOK COVER" text). It is always added with
        is_cover=True and sensible dimensions.
        """
        if self._coverfile is not None:
            return
        data = _load_default_cover_bytes()
        # Use known dimensions for the shipped asset (fast path).
        dims = _DEFAULT_COVER_DIMS
        # As a safety net, try to parse if the asset ever changes.
        parsed = _jpeg_dimensions(data)
        if parsed is not None:
            dims = parsed
        self.add_image_content("cover.jpg", data, is_cover=True, img_dims=dims)

    def close(self):
        """Write the navigation document and package file, then close the archive."""
        self._ensure_cover()
        self._generate_nav_page()
        self._generate_content_opf()
        self._zipfile.close()

    def _generate_content_opf(self):
        # _ensure_cover() in close() guarantees this is never None for normal use.
        if self._coverfile is None:
            raise Exception("Internal error: no cover was set (this should be impossible)")
        if len(self._spine) == 0:
            raise Exception("Spine is empty!")

        parts: list[str] = []
        parts.append(
            f"""<?xml version="1.0" encoding="utf-8"?>
<package version="3.0" unique-identifier="BookId" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:language>en</dc:language>
    <dc:creator id="cre">{self._author}</dc:creator>
    <meta refines="#cre" property="role" scheme="marc:relators">aut</meta>
    <dc:date>{self._pubyear}</dc:date>
    <dc:title>{self._title}</dc:title>
    <meta property="dcterms:modified">{_datetime.date.today().isoformat()}T12:00:00Z</meta>
    <dc:identifier id="BookId">urn:uuid:{_uuid.uuid4()}</dc:identifier>
    <meta name="cover" content="{self._coverfile}" />
  </metadata>
  <manifest>"""
        )
        for item in self._contents:
            propstr = f' properties="{item.properties}"' if item.properties else ""
            oebps_relative = item.zip_path[6:]
            parts.append(
                f'<item id="{item.fname}" href="{oebps_relative}" media-type="{item.media_type}"{propstr}/>'
            )
        parts.append(" </manifest>")
        parts.append("  <spine>")
        parts.append(f'    <itemref idref="{self._spine[0]}"/>')
        parts.append('    <itemref idref="nav.xhtml" linear="no"/>')
        for pg in self._spine[1:]:
            parts.append(f'    <itemref idref="{pg}"/>')
        parts.append("  </spine>")
        parts.append("</package>")
        self._zipfile.writestr(self.content_path(), "\n".join(parts))

    def _generate_nav_page(self):
        """Create the nav.xhtml file (EPUB Navigation Document)."""
        resolved: list[tuple[int, str, str]] = []
        for entry in self._toc_entries:
            href = self._resolve_target(entry.target)
            resolved.append((entry.level, href, entry.text))

        toc_inner = self._render_nested_toc(resolved)

        parts: list[str] = []
        parts.append(
            f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">
<head>
  <title>ePub NAV</title>
  <style>
nav#landmarks {{ display:none; }}
nav#page-list {{ display:none; }}
ol {{ list-style-type: none; }}
  </style>
</head>
<body epub:type="frontmatter">
  <nav epub:type="toc" id="toc" role="doc-toc">
    <h1>Table of Contents</h1>
{toc_inner}
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
</html>"""
        )
        xhtml_fname = "nav.xhtml"
        zip_path = self.xhtml_path(xhtml_fname)
        self._zipfile.writestr(zip_path, "\n".join(parts))
        self._contents.append(
            _ContentItem(
                fname=xhtml_fname,
                zip_path=zip_path,
                media_type=self.media_type(xhtml_fname),
                properties="nav",
            )
        )

    def _resolve_target(self, target: str | int) -> str:
        if isinstance(target, int):
            if target < 1 or target > len(self._spine):
                raise Exception(
                    f"Chapter number {target} is out of range (have {len(self._spine)} spine items)"
                )
            fname = self._spine[target - 1]
            return self.xhtml_path(fname, relative=True)
        if isinstance(target, str):
            # Be forgiving: "chapter3" and "chapter3.xhtml" both work
            normalized = _ensure_xhtml_extension(target)
            return self.xhtml_path(normalized, relative=True)
        raise TypeError(f"TOC target must be str (filename) or int (chapter number), got {type(target)}")

    def _render_nested_toc(self, entries: list[tuple[int, str, str]]) -> str:
        """Return a properly nested <ol>...</ol> block for the TOC nav."""
        if not entries:
            return "    <ol>\n    </ol>"

        # Validation: no level skips > +1
        prev = 0
        for lvl, _, _ in entries:
            if lvl > prev + 1:
                raise ValueError(
                    f"Invalid TOC nesting: level jumped from {prev} to {lvl}. "
                    "Levels must increase by at most 1 between consecutive entries."
                )
            if not 1 <= lvl <= 3:
                raise ValueError(f"TOC level must be 1, 2, or 3 (got {lvl})")
            prev = lvl

        html: list[str] = []
        level = 0
        for lvl, href, text in entries:
            delta = lvl - level
            if delta > 0:
                html.extend(["<ol>"] * delta)
            elif delta < 0:
                html.append("</li></ol>" * (-delta))
                html.append("</li>")
            else:
                if level > 0:
                    html.append("</li>")
            html.append(f'<li><a href="{href}">{text}</a>')
            level = lvl

        html.append("</li></ol>" * level)
        # Indent for readability inside the nav template
        return "\n    ".join(html)

    def add_toc_entry(self, text: str, target: str | int, level: int = 1):
        """Add a (possibly nested) entry to the Table of Contents.

        target:
            - str: the xhtml filename (e.g. "chapter03" or "chapter03.xhtml" — the
              .xhtml extension is added automatically if missing)
            - int: 1-based chapter number = position in the spine at close() time

        level: 1 (top), 2, or 3 (deepest nesting supported).
        """
        if not 1 <= level <= 3:
            raise ValueError("TOC level must be 1, 2, or 3")
        self._toc_entries.append(_TocEntry(level=level, target=target, text=text))

    def add_image_content(
        self,
        img_fname: str,
        img_data: bytes,
        is_cover: bool = False,
        img_dims: tuple[int, int] | None = None,
    ):
        """Add an image file to the EPUB.

        If is_cover=True (or this is the first image), it becomes the cover.
        Provide img_dims when you will later call add_fullpage_pic for this image.
        """
        if self._coverfile is None or is_cover:
            self._coverfile = img_fname
        if img_dims is not None:
            self._img_dims[img_fname] = img_dims
        props = "cover-image" if is_cover else ""
        zip_path = self.img_path(img_fname)
        self._zipfile.writestr(zip_path, img_data)
        self._contents.append(
            _ContentItem(
                fname=img_fname,
                zip_path=zip_path,
                media_type=self.media_type(img_fname),
                properties=props,
            )
        )

    def add_fullpage_pic(self, xhtml_fname: str, img_fname: str):
        """Add a full-page image page (wrapped in an SVG for proper scaling on all readers).

        You *must* have previously called add_image_content with img_dims for this image.
        If `xhtml_fname` has no extension, ".xhtml" is appended automatically.
        """
        xhtml_fname = _ensure_xhtml_extension(xhtml_fname)
        try:
            w, h = self._img_dims[img_fname]
        except KeyError:
            raise Exception(f"Don't have dimensions for the image {img_fname}!")

        content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>{_Path(img_fname).stem}</title>
</head>
<body>
  <div style="height: 100vh; text-align: center; padding: 0pt; margin: 0pt;">
    <svg xmlns="http://www.w3.org/2000/svg" height="100%" preserveAspectRatio="xMidYMid meet" version="1.1" viewBox="0 0 {w} {h}" width="100%" xmlns:xlink="http://www.w3.org/1999/xlink">
      <image width="{w}" height="{h}" xlink:href="{self.img_path(img_fname, relative=True)}"/>
    </svg>
  </div>
</body>
</html>"""
        self.add_xhtml_content(xhtml_fname, content, "svg")

    def add_xhtml_content(self, xhtml_fname: str, xhtml_content: str, properties: str = ""):
        """Add a complete XHTML document (you supply the full <html>...</html>).

        If `xhtml_fname` has no extension, ".xhtml" is appended automatically.
        """
        xhtml_fname = _ensure_xhtml_extension(xhtml_fname)
        zip_path = self.xhtml_path(xhtml_fname)
        self._zipfile.writestr(zip_path, xhtml_content)
        self._contents.append(
            _ContentItem(
                fname=xhtml_fname,
                zip_path=zip_path,
                media_type=self.media_type(xhtml_fname),
                properties=properties,
            )
        )
        self._spine.append(xhtml_fname)

    # --- New easy-mode APIs (the main improvements) ---

    def add_stylesheet(self, css_fname: str, css_data: str | bytes):
        """Add a CSS stylesheet. Can be called multiple times.

        All registered stylesheets are automatically linked (in addition order)
        from any page created with add_xhtml_body().

        If `css_fname` has no extension, ".css" is appended automatically.
        """
        css_fname = _ensure_css_extension(css_fname)
        data = css_data.encode("utf-8") if isinstance(css_data, str) else css_data
        zip_path = self.css_path(css_fname)
        self._zipfile.writestr(zip_path, data)
        self._contents.append(
            _ContentItem(
                fname=css_fname,
                zip_path=zip_path,
                media_type=self.media_type(css_fname),
                properties="",
            )
        )
        self._stylesheets.append(css_fname)

    def _wrap_xhtml_body(self, body: str, title: str) -> str:
        """Produce a complete, standards-friendly EPUB XHTML document around the given body fragment."""
        links = []
        for css in self._stylesheets:
            href = self.css_path(css, relative=True)
            links.append(f'  <link rel="stylesheet" type="text/css" href="{href}"/>')
        css_block = "\n".join(links) + ("\n" if links else "")

        return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">
<head>
  <title>{title}</title>
{css_block}</head>
<body>
{body}
</body>
</html>"""

    def add_xhtml_body(
        self,
        xhtml_fname: str,
        body_content: str,
        title: str | None = None,
        properties: str = "",
    ):
        """Add an XHTML page by supplying only the inner body content.

        The library wraps it with a standard EPUB3 XHTML header/footer.
        If any stylesheets have been added via add_stylesheet(), they are
        automatically referenced via <link> elements.

        If `xhtml_fname` has no extension, ".xhtml" is appended automatically.
        """
        doc_title = title or self._title
        full = self._wrap_xhtml_body(body_content, doc_title)
        self.add_xhtml_content(xhtml_fname, full, properties)


# Convenience re-export
__all__ = ["EpubWriter"]
