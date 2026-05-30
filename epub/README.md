# rwt_epub

A tiny, pure-Python library for writing EPUB 3 files.

- Add JPEG/PNG/GIF/WebP/SVG images (all EPUB 3.3 core image types)
- Add raw XHTML or just body content (the library supplies a clean header/footer)
- Register one or more CSS stylesheets — they are automatically linked from body-only pages
- Full-page images wrapped in SVG for reliable scaling
- Clean 3-level Table of Contents with targets by filename **or** by 1-based chapter number (spine order)
- 100% stdlib, no dependencies, works great with `uv`

## Installation

```bash
uv pip install rwt-epub
# or
uv add rwt-epub
```

## Quickstart

```python
from rwt_epub import EpubWriter

with EpubWriter("mybook.epub", "My Great Novel", "Jane Doe", 2025) as w:
    # Cover image (provide dimensions if you will use full-page SVG later)
    w.add_image_content("cover.jpg", cover_jpeg_bytes, is_cover=True, img_dims=(1200, 1600))

    # Optional: a CSS file (can call multiple times)
    w.add_stylesheet("book.css", "body { font-family: Georgia, serif; line-height: 1.5; }")

    # Easy mode: just give body content; header + CSS link are automatic
    w.add_xhtml_body(
        "ch01.xhtml",
        "<h1>Chapter One</h1><p>It was a dark and stormy night...</p>",
        title="Chapter One"
    )

    # You can still supply fully-formed XHTML when you need more control
    w.add_xhtml_content("colophon.xhtml", """<?xml ... full document ...""")

    # TOC: mix filename targets and 1-based chapter numbers (spine order at close time)
    w.add_toc_entry("Chapter One", target=2, level=1)      # 2nd spine item
    w.add_toc_entry("Colophon", target="colophon.xhtml", level=1)
```

## Table of Contents with Nesting & Chapter Numbers

```python
w.add_toc_entry("Part I", target=2, level=1)
w.add_toc_entry("The Beginning", target=3, level=2)
w.add_toc_entry("The Middle", target=4, level=2)
w.add_toc_entry("Part II", target=5, level=1)
w.add_toc_entry("The End", target=6, level=3)   # up to 3 levels deep
```

Chapter numbers are simply the 1-based position in the spine at the moment you call `close()` (or exit the context manager). Add your front-matter (cover page, title page, etc.) first, then your chapters — the numbers will be obvious.

## Full-Page Images

```python
w.add_image_content("map.png", png_bytes, img_dims=(2400, 3200))
w.add_fullpage_pic("map-page.xhtml", "map.png")   # emits a properly scaling SVG wrapper
```

## Media Types

`EpubWriter.media_type("foo.webp")` etc. now returns the correct EPUB core type for:

`gif`, `jpeg`/`jpg`, `png`, `svg`, `webp`, `xhtml`/`html`/`htm`, `css`.

## Small Conveniences

- **Default cover**: If you never call `add_image_content(..., is_cover=True)`, a real packaged JPEG (leather texture with "BOOK COVER" lettering) is automatically embedded and registered as the cover image. The file lives at `src/rwt_epub/default_cover.jpg` inside the distribution.
- **Auto extensions**: You can omit the extension on XHTML and CSS filenames:
  ```python
  w.add_xhtml_body("chapter1", "<h1>...</h1>")   # becomes chapter1.xhtml
  w.add_stylesheet("book", "body { ... }")       # becomes book.css
  w.add_toc_entry("Ch 1", "chapter1")            # resolves correctly
  ```
  (Image filenames are left exactly as you provide them.)

## Building from Source

```bash
uv build
```

This uses the native `uv_build` backend and produces a clean wheel containing only the `rwt_epub` package.

## License

MIT
