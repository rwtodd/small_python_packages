# rwt_rfonts

Authentic **IBM EGA/VGA Code Page 437** bitmap fonts and a fast packed-pixel
text blitter for use with [`rwt_rconsole`](../retro-console).

Stock fonts (VGA ROM layout: 256 glyphs × height bytes, MSB = left pixel):

| Font | Size | Typical modes |
|------|------|----------------|
| `VGA_8x8` / `CGA_8x8` | 8×8 | 320×200 (40×25), 320×240 (40×30) |
| `EGA_8x14` | 8×14 | EGA 640×350 |
| `VGA_8x16` | 8×16 | **80×25 text**, 640×400 (80×25), 640×480 (80×30) |

Default text font: `VGA_8x16` (`DEFAULT_TEXT_FONT`).

## Install

```bash
cd retro-fonts
uv sync --extra dev
```

Builds a small C extension (`rwt_rfonts._blit`, abi3) — same pattern as
`rwt_spritz` / `rwt_bascat`. **No pure-Python blit fallback**; a compiler is
required to install.

## Quick start

```python
from rwt_rfonts import VGA_8x16, put_string, put_string_fb, encode_cp437

# Raw buffer (width, height, bit_depth must match packing)
buf = bytearray(640 * 400)  # 8 bpp
put_string(
    VGA_8x16, buf,
    size=(640, 400), bit_depth=8,
    x=0, y=0,
    text="Hello, VGA!",
    fg=15, bg=1,           # bg=None → transparent
)

# Character cells: convert then blit (same API)
x, y = VGA_8x16.cell_to_pixel(col=10, row=2)
put_string(VGA_8x16, buf, size=(640, 400), bit_depth=8, x=x, y=y, text="cell", fg=14, bg=0)

# With rwt_rconsole.FrameBuffer (size + bit_depth taken from the buffer)
put_string_fb(VGA_8x16, display.buffer, x, y, "Score ♥", fg=12, bg=None)
# or raw CP437:
put_string_fb(VGA_8x16, display.buffer, x, y, b"\x03\x04\x05\x06", fg=14, bg=1)
```

Unicode strings are encoded with Python’s `cp437` codec (`encode_cp437`), so
box-drawing and DOS symbols work when they have CP437 mappings.

## Bit depths

Matches `rwt_rconsole` packing:

| bpp | Notes |
|-----|--------|
| 8 | One palette index per byte |
| 4 | High nibble = left pixel; even width |
| 1 | MSB = left; width ÷ 8; **two** indices (0 and 1). Reverse video `fg=0, bg=1` is supported |

## Demo (optional, needs rconsole + Metal)

```bash
uv pip install -e "../retro-console[metal]"
uv run python examples/text_demo.py --mode 640x400 --crt
```

The demo draws double-line frames, blocks, card suits, and other graphical CP437
glyphs.

## Tests

```bash
uv run --extra dev pytest
```

## Font provenance

See [`src/rwt_rfonts/data/PROVENANCE.md`](src/rwt_rfonts/data/PROVENANCE.md).
Binaries are IBM EGA/VGA ROM extracts (via [spacerace/romfont](https://github.com/spacerace/romfont)).

## License

MIT (library code). Embedded ROM fonts: see provenance note above.
