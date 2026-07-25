"""Stock font loading and geometry."""

from __future__ import annotations

import hashlib

from rwt_rfonts import (
    CGA_8x8,
    DEFAULT_TEXT_FONT,
    EGA_8x14,
    VGA_8x8,
    VGA_8x16,
    decode_cp437,
    encode_cp437,
    recommend_font,
)


def test_stock_sizes() -> None:
    assert len(VGA_8x8.glyphs) == 256 * 8
    assert len(EGA_8x14.glyphs) == 256 * 14
    assert len(VGA_8x16.glyphs) == 256 * 16
    assert VGA_8x8.width == 8 and VGA_8x8.height == 8
    assert EGA_8x14.height == 14
    assert VGA_8x16.height == 16
    assert CGA_8x8 is VGA_8x8
    assert DEFAULT_TEXT_FONT is VGA_8x16


def test_glyph_a_has_ink() -> None:
    for font in (VGA_8x8, EGA_8x14, VGA_8x16):
        g = font.glyph_bytes(ord("A"))
        assert any(b != 0 for b in g)


def test_cell_to_pixel() -> None:
    assert VGA_8x16.cell_to_pixel(0, 0) == (0, 0)
    assert VGA_8x16.cell_to_pixel(10, 3) == (80, 48)
    assert VGA_8x8.cell_to_pixel(39, 24) == (312, 192)


def test_cells_for() -> None:
    assert VGA_8x8.cells_for(320, 200) == (40, 25)
    assert VGA_8x8.cells_for(320, 240) == (40, 30)
    assert VGA_8x16.cells_for(640, 400) == (80, 25)
    assert VGA_8x16.cells_for(640, 480) == (80, 30)


def test_recommend_font() -> None:
    assert recommend_font(320, 200) is VGA_8x8
    assert recommend_font(320, 240) is VGA_8x8
    assert recommend_font(640, 350) is EGA_8x14
    assert recommend_font(640, 400) is VGA_8x16
    assert recommend_font(640, 480) is VGA_8x16


def test_known_md5() -> None:
    assert hashlib.md5(VGA_8x8.glyphs).hexdigest() == "36addababf8830d29e7502e7a4d4d9f8"
    assert hashlib.md5(EGA_8x14.glyphs).hexdigest() == "8bcbaf14d1c2729dbbbd486d0929f98c"
    assert hashlib.md5(VGA_8x16.glyphs).hexdigest() == "10c3d174722de153243d60a06d29865a"


def test_cp437_roundtrip_ascii() -> None:
    s = "Hello, VGA!"
    assert decode_cp437(encode_cp437(s)) == s


def test_cp437_box_drawing() -> None:
    # Single-line box corners / sides in Unicode → CP437
    s = "┌─┐│└─┘"
    b = encode_cp437(s)
    assert len(b) == len(s)
    assert decode_cp437(b) == s


def test_cp437_graphical_low_and_blocks() -> None:
    # C0 glyph forms + blocks (stdlib cp437 cannot encode these)
    s = "☺☻♥♦♣♠♪♫░▒▓█"
    assert encode_cp437(s) == bytes(
        [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x0D, 0x0E, 0xB0, 0xB1, 0xB2, 0xDB]
    )
    assert decode_cp437(encode_cp437(s)) == s
