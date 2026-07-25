"""Stock IBM EGA/VGA CP437 fonts and cell geometry helpers."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Final

_DATA = resources.files("rwt_rfonts").joinpath("data")


def _load_bin(name: str) -> bytes:
    return _DATA.joinpath(name).read_bytes()


@dataclass(frozen=True, slots=True)
class Font:
    """An 8-pixel-wide CP437 bitmap font (VGA ROM layout).

    Parameters
    ----------
    name:
        Human-readable identifier.
    width:
        Glyph width in pixels (8 for stock fonts).
    height:
        Glyph height in pixels (8, 14, or 16 for stock fonts).
    glyphs:
        ``256 * height * ceil(width/8)`` bytes; for width 8, ``256 * height``.
    """

    name: str
    width: int
    height: int
    glyphs: bytes

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Font width and height must be positive.")
        bytes_per_row = (self.width + 7) // 8
        expected = 256 * self.height * bytes_per_row
        if len(self.glyphs) != expected:
            raise ValueError(
                f"glyphs length {len(self.glyphs)} does not match "
                f"256×{self.height}×{bytes_per_row} = {expected}."
            )

    @property
    def cell_size(self) -> tuple[int, int]:
        """``(width, height)`` of one character cell in pixels."""
        return self.width, self.height

    def cell_to_pixel(self, col: int, row: int) -> tuple[int, int]:
        """Convert character-cell ``(col, row)`` to absolute upper-left pixel ``(x, y)``."""
        return col * self.width, row * self.height

    def cells_for(self, pixel_width: int, pixel_height: int) -> tuple[int, int]:
        """How many full character cells fit in a ``pixel_width`` × ``pixel_height`` display."""
        if pixel_width < 0 or pixel_height < 0:
            raise ValueError("pixel dimensions must be non-negative.")
        return pixel_width // self.width, pixel_height // self.height

    def glyph_bytes(self, code: int) -> memoryview:
        """Return a memoryview of one glyph's row bytes (``code & 0xFF``)."""
        code &= 0xFF
        bytes_per_row = (self.width + 7) // 8
        stride = self.height * bytes_per_row
        start = code * stride
        return memoryview(self.glyphs)[start : start + stride]


def _font_from_data(name: str, width: int, height: int, filename: str) -> Font:
    return Font(name=name, width=width, height=height, glyphs=_load_bin(filename))


@lru_cache(maxsize=1)
def _stock() -> dict[str, Font]:
    return {
        "vga_8x8": _font_from_data("IBM VGA 8x8", 8, 8, "ibm_vga_8x8.bin"),
        "ega_8x14": _font_from_data("IBM EGA 8x14", 8, 14, "ibm_ega_8x14.bin"),
        "vga_8x16": _font_from_data("IBM VGA 8x16", 8, 16, "ibm_vga_8x16.bin"),
    }


def _get(key: str) -> Font:
    return _stock()[key]


# Lazy module-level accessors via properties on a small namespace would be
# unusual; expose callables that return cached Fonts plus module attributes
# populated at first import of stock (cheap: three small bin reads).

VGA_8x8: Final[Font] = _get("vga_8x8")
CGA_8x8: Final[Font] = VGA_8x8  # same ROM set used for CGA-compatible modes
EGA_8x14: Final[Font] = _get("ega_8x14")
VGA_8x16: Final[Font] = _get("vga_8x16")

DEFAULT_TEXT_FONT: Final[Font] = VGA_8x16
"""Default VGA 80×25 text-mode font (8×16)."""


def recommend_font(width: int, height: int) -> Font:
    """Pick a stock font for a graphics mode resolution.

    * Height ≤ 240 → 8×8 (320×200, 320×240, …)
    * Height ≤ 350 → 8×14 (EGA 640×350)
    * else → 8×16 (640×400, 640×480, …)
    """
    if height <= 240:
        return VGA_8x8
    if height <= 350:
        return EGA_8x14
    return VGA_8x16


def load_font(path: str | Path, *, width: int = 8, height: int, name: str | None = None) -> Font:
    """Load a raw ROM-layout font binary from disk."""
    p = Path(path)
    data = p.read_bytes()
    return Font(name=name or p.stem, width=width, height=height, glyphs=data)
