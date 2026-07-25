"""Geometry-aware packed framebuffer (1 / 4 / 8 bpp)."""

from __future__ import annotations

from .buffer import SharedByteBuffer
from .pixel_packing import get_pixel, set_pixel
from .types import BitDepth, Size2D
from .video_math import buffer_length


class FrameBuffer:
    """Packed paletted VRAM with known size and bit depth.

    Supports the buffer protocol (delegates to the underlying storage),
    pixel access via ``fb[x, y]``, and raw byte views for bulk fills.

    Parameters
    ----------
    size:
        Source resolution in pixels.
    bit_depth:
        Packed bit depth.
    data:
        Optional pre-allocated storage (e.g. Metal shared buffer).
        If omitted, a managed ``SharedByteBuffer`` is allocated.
    """

    __slots__ = ("size", "bit_depth", "data")

    def __init__(
        self,
        size: Size2D,
        bit_depth: BitDepth,
        data: SharedByteBuffer | None = None,
    ) -> None:
        expected = buffer_length(size, bit_depth)
        if data is None:
            data = SharedByteBuffer(expected)
        elif len(data) != expected:
            raise ValueError(
                f"Buffer length {len(data)} does not match "
                f"{size.width}×{size.height} @ {int(bit_depth)} bpp ({expected} bytes)."
            )
        self.size = size
        self.bit_depth = bit_depth
        self.data = data

    def __len__(self) -> int:
        return len(self.data)

    def __buffer__(self, flags: int) -> memoryview:
        return self.data.__buffer__(flags)

    def __getitem__(self, key: tuple[int, int]) -> int:
        x, y = key
        return get_pixel(self.data, self.bit_depth, self.size, x, y)

    def __setitem__(self, key: tuple[int, int], color_index: int) -> None:
        x, y = key
        set_pixel(self.data, self.bit_depth, self.size, x, y, color_index)

    @property
    def address(self) -> int:
        return self.data.address

    @property
    def dirty(self) -> bool:
        return self.data.dirty

    def mark_dirty(self) -> None:
        self.data.mark_dirty()

    def clear_dirty(self) -> None:
        self.data.clear_dirty()

    @property
    def view(self) -> memoryview:
        """Writable uint8 memoryview of packed VRAM; marks dirty."""
        return self.data.view

    def fill(self, value: int = 0) -> None:
        """Fill packed VRAM bytes (not palette indices, except at 8 bpp)."""
        self.data.fill(value)
