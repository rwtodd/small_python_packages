"""Packed pixel read/write for 1 / 4 / 8 bpp row-major buffers (no padding).

1 bpp: MSB is the leftmost pixel.
4 bpp: high nibble is the left pixel.
"""

from __future__ import annotations

from .buffer import SharedByteBuffer
from .types import BitDepth, Size2D
from .video_math import palette_length, pitch as row_pitch


def _as_mv(buffer: SharedByteBuffer | memoryview | bytearray | bytes) -> memoryview:
    if isinstance(buffer, SharedByteBuffer):
        return buffer.view
    if isinstance(buffer, memoryview):
        return buffer.cast("B") if buffer.format != "B" else buffer
    return memoryview(buffer).cast("B")


def _check_bounds(size: Size2D, x: int, y: int) -> None:
    if x < 0 or y < 0 or x >= size.width or y >= size.height:
        raise IndexError(f"Pixel ({x},{y}) outside {size.width}×{size.height}.")


def set_pixel(
    buffer: SharedByteBuffer | memoryview | bytearray,
    bit_depth: BitDepth,
    size: Size2D,
    x: int,
    y: int,
    color_index: int,
) -> None:
    """Write a palette index at (x, y)."""
    _check_bounds(size, x, y)
    max_index = palette_length(bit_depth) - 1
    if color_index < 0 or color_index > max_index:
        raise ValueError(f"Color index must be 0..{max_index}.")

    mv = _as_mv(buffer)
    rp = row_pitch(size, bit_depth)
    row = y * rp

    if bit_depth is BitDepth.BPP8:
        mv[row + x] = color_index
    elif bit_depth is BitDepth.BPP4:
        i = row + x // 2
        existing = mv[i]
        if x % 2 == 0:
            mv[i] = (existing & 0x0F) | ((color_index & 0x0F) << 4)
        else:
            mv[i] = (existing & 0xF0) | (color_index & 0x0F)
    elif bit_depth is BitDepth.BPP1:
        i = row + x // 8
        bit = 7 - (x % 8)
        mask = 1 << bit
        existing = mv[i]
        if color_index != 0:
            mv[i] = existing | mask
        else:
            mv[i] = existing & ~mask
    else:
        raise ValueError(f"Unsupported bit depth: {int(bit_depth)}")

    if isinstance(buffer, SharedByteBuffer):
        buffer.mark_dirty()


def get_pixel(
    buffer: SharedByteBuffer | memoryview | bytearray | bytes,
    bit_depth: BitDepth,
    size: Size2D,
    x: int,
    y: int,
) -> int:
    """Read a palette index at (x, y)."""
    _check_bounds(size, x, y)
    mv = _as_mv(buffer)
    rp = row_pitch(size, bit_depth)
    row = y * rp

    if bit_depth is BitDepth.BPP8:
        return int(mv[row + x])
    if bit_depth is BitDepth.BPP4:
        b = int(mv[row + x // 2])
        return (b >> 4) if x % 2 == 0 else (b & 0x0F)
    if bit_depth is BitDepth.BPP1:
        b = int(mv[row + x // 8])
        bit = 7 - (x % 8)
        return 1 if (b >> bit) & 1 else 0
    raise ValueError(f"Unsupported bit depth: {int(bit_depth)}")
