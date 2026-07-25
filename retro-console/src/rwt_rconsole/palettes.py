"""Stock palettes useful for 1 / 4 / 8 bpp modes."""

from __future__ import annotations

from .types import BitDepth, RgbColor


def _rgb(r: int, g: int, b: int) -> RgbColor:
    return RgbColor(r, g, b)


monochrome: tuple[RgbColor, ...] = (
    _rgb(0, 0, 0),
    _rgb(255, 255, 255),
)

cga: tuple[RgbColor, ...] = (
    _rgb(0, 0, 0),
    _rgb(0, 0, 170),
    _rgb(0, 170, 0),
    _rgb(0, 170, 170),
    _rgb(170, 0, 0),
    _rgb(170, 0, 170),
    _rgb(170, 85, 0),
    _rgb(170, 170, 170),
    _rgb(85, 85, 85),
    _rgb(85, 85, 255),
    _rgb(85, 255, 85),
    _rgb(85, 255, 255),
    _rgb(255, 85, 85),
    _rgb(255, 85, 255),
    _rgb(255, 255, 85),
    _rgb(255, 255, 255),
)

ega: tuple[RgbColor, ...] = cga


def _build_vga() -> tuple[RgbColor, ...]:
    colors: list[RgbColor] = [RgbColor(0, 0, 0)] * 256
    for i in range(16):
        colors[i] = cga[i]
    for i in range(16):
        v = i * 255 // 15
        colors[16 + i] = _rgb(v, v, v)
    idx = 32
    for r in range(6):
        for g in range(6):
            for b in range(6):
                if idx < 248:
                    colors[idx] = _rgb(r * 255 // 5, g * 255 // 5, b * 255 // 5)
                    idx += 1
    for i in range(248, 256):
        colors[i] = _rgb(0, 0, 0)
    return tuple(colors)


vga: tuple[RgbColor, ...] = _build_vga()


def for_bit_depth(bit_depth: BitDepth) -> tuple[RgbColor, ...]:
    """Pick a default palette sized for the given bit depth."""
    if bit_depth is BitDepth.BPP1:
        return monochrome
    if bit_depth is BitDepth.BPP4:
        return ega
    if bit_depth is BitDepth.BPP8:
        return vga
    raise ValueError(f"Unsupported bit depth: {int(bit_depth)}")
