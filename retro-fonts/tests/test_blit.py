"""Blit correctness for 1/4/8 bpp, transparency, reverse video, clipping."""

from __future__ import annotations

from dataclasses import dataclass

from rwt_rfonts import VGA_8x8, put_char, put_string, put_string_fb


def _get_pixel_8(buf: bytearray, w: int, x: int, y: int) -> int:
    return buf[y * w + x]


def _get_pixel_4(buf: bytearray, w: int, x: int, y: int) -> int:
    pitch = w // 2
    b = buf[y * pitch + x // 2]
    return (b >> 4) if x % 2 == 0 else (b & 0x0F)


def _get_pixel_1(buf: bytearray, w: int, x: int, y: int) -> int:
    pitch = w // 8
    b = buf[y * pitch + x // 8]
    bit = 7 - (x % 8)
    return 1 if (b >> bit) & 1 else 0


def test_put_char_8bpp_opaque() -> None:
    w, h = 16, 8
    buf = bytearray(w * h)  # filled with 0
    put_char(VGA_8x8, buf, size=(w, h), bit_depth=8, x=0, y=0, code=ord("A"), fg=7, bg=1)
    g = VGA_8x8.glyph_bytes(ord("A"))
    for row in range(8):
        bits = g[row]
        for col in range(8):
            expected = 7 if bits & (0x80 >> col) else 1
            assert _get_pixel_8(buf, w, col, row) == expected


def test_put_char_8bpp_transparent() -> None:
    w, h = 16, 8
    buf = bytearray([9] * (w * h))
    put_char(VGA_8x8, buf, size=(w, h), bit_depth=8, x=0, y=0, code=ord("A"), fg=2, bg=None)
    g = VGA_8x8.glyph_bytes(ord("A"))
    for row in range(8):
        bits = g[row]
        for col in range(8):
            if bits & (0x80 >> col):
                assert _get_pixel_8(buf, w, col, row) == 2
            else:
                assert _get_pixel_8(buf, w, col, row) == 9  # untouched


def test_put_string_advance() -> None:
    w, h = 64, 8
    buf = bytearray(w * h)
    end = put_string(
        VGA_8x8, buf, size=(w, h), bit_depth=8, x=8, y=0, text="Hi", fg=15, bg=0
    )
    assert end == 8 + 2 * 8


def test_cell_to_pixel_blit() -> None:
    w, h = 80, 25  # not multiple of font for display; small buffer
    # Use 40x16 so two cell rows fit with 8x8
    w, h = 40, 16
    buf = bytearray(w * h)
    x, y = VGA_8x8.cell_to_pixel(1, 1)
    assert (x, y) == (8, 8)
    put_string(VGA_8x8, buf, size=(w, h), bit_depth=8, x=x, y=y, text="X", fg=1, bg=0)
    # Some ink should appear in the second cell
    assert any(buf[8 * w + 8 : 8 * w + 16])


def test_4bpp() -> None:
    w, h = 16, 8
    buf = bytearray((w // 2) * h)
    put_char(VGA_8x8, buf, size=(w, h), bit_depth=4, x=0, y=0, code=ord("A"), fg=0xE, bg=0x1)
    g = VGA_8x8.glyph_bytes(ord("A"))
    for row in range(8):
        bits = g[row]
        for col in range(8):
            expected = 0xE if bits & (0x80 >> col) else 0x1
            assert _get_pixel_4(buf, w, col, row) == expected


def test_1bpp_reverse_video() -> None:
    """1 bpp still has two palette indices; reverse video fg=0 bg=1 must work."""
    w, h = 16, 8
    buf = bytearray((w // 8) * h)  # all zeros
    put_char(VGA_8x8, buf, size=(w, h), bit_depth=1, x=0, y=0, code=ord("A"), fg=0, bg=1)
    g = VGA_8x8.glyph_bytes(ord("A"))
    for row in range(8):
        bits = g[row]
        for col in range(8):
            expected = 0 if bits & (0x80 >> col) else 1
            assert _get_pixel_1(buf, w, col, row) == expected


def test_1bpp_normal() -> None:
    w, h = 16, 8
    buf = bytearray((w // 8) * h)
    put_char(VGA_8x8, buf, size=(w, h), bit_depth=1, x=0, y=0, code=ord("A"), fg=1, bg=0)
    g = VGA_8x8.glyph_bytes(ord("A"))
    for row in range(8):
        bits = g[row]
        for col in range(8):
            expected = 1 if bits & (0x80 >> col) else 0
            assert _get_pixel_1(buf, w, col, row) == expected


def test_clipping() -> None:
    w, h = 8, 8
    buf = bytearray(w * h)
    # Partially off the right edge — should not raise
    put_string(VGA_8x8, buf, size=(w, h), bit_depth=8, x=4, y=0, text="AB", fg=3, bg=0)
    assert any(b == 3 for b in buf)


def test_put_string_fb() -> None:
    @dataclass
    class Size:
        width: int
        height: int

    @dataclass
    class FakeFB:
        size: Size
        bit_depth: int
        data: bytearray
        dirty: bool = False

        def mark_dirty(self) -> None:
            self.dirty = True

        def __buffer__(self, flags: int):
            return memoryview(self.data)

    w, h = 32, 8
    fb = FakeFB(Size(w, h), 8, bytearray(w * h))
    end = put_string_fb(VGA_8x8, fb, 0, 0, "OK", fg=5, bg=0)
    assert end == 16
    assert fb.dirty
    assert any(b == 5 for b in fb.data)


def test_box_drawing_bytes() -> None:
    # CP437 single-line box: 0xDA 0xC4 0xBF / 0xB3 / 0xC0 0xC4 0xD9
    w, h = 24, 8
    buf = bytearray(w * h)
    put_string(
        VGA_8x8,
        buf,
        size=(w, h),
        bit_depth=8,
        x=0,
        y=0,
        text=bytes([0xDA, 0xC4, 0xBF]),
        fg=15,
        bg=0,
    )
    assert any(b == 15 for b in buf)
