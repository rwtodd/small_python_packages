"""In-memory palette (tests and headless use)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .framebuffer import FrameBuffer
from .palettes import for_bit_depth
from .types import BitDepth, RgbColor, Size2D
from .video_math import palette_length


class Palette:
    """Mutable RGB palette with dirty tracking.

    Indexing accepts ``RgbColor`` or ``(r, g, b)`` tuples.
    """

    __slots__ = ("_colors", "_dirty", "_on_change")

    def __init__(
        self,
        count: int | BitDepth,
        initial: Sequence[RgbColor | tuple[int, int, int]] | None = None,
        *,
        on_change: Callable[[int, RgbColor], None] | None = None,
    ) -> None:
        if isinstance(count, BitDepth):
            n = palette_length(count)
            if initial is None:
                initial = for_bit_depth(count)
        else:
            n = count

        if n < 1:
            raise ValueError("Palette count must be at least 1.")

        self._colors: list[RgbColor] = [RgbColor(0, 0, 0)] * n
        if initial is not None:
            for i, c in enumerate(initial[:n]):
                self._colors[i] = RgbColor.from_any(c)
        self._dirty = True
        self._on_change = on_change

    def __len__(self) -> int:
        return len(self._colors)

    def __getitem__(self, index: int) -> RgbColor:
        return self._colors[index]

    def __setitem__(self, index: int, value: RgbColor | tuple[int, int, int]) -> None:
        color = RgbColor.from_any(value)
        self._colors[index] = color
        self._dirty = True
        if self._on_change is not None:
            self._on_change(index, color)

    def __iter__(self):
        return iter(self._colors)

    @property
    def dirty(self) -> bool:
        return self._dirty

    def clear_dirty(self) -> None:
        self._dirty = False

    def mark_dirty(self) -> None:
        self._dirty = True

    def copy(self) -> list[RgbColor]:
        """Return a shallow copy of palette entries."""
        return list(self._colors)

    def update(self, source: Sequence[RgbColor | tuple[int, int, int]]) -> None:
        """Replace the leading entries from *source*."""
        if len(source) > len(self._colors):
            raise ValueError("Source has more colors than the palette.")
        for i, c in enumerate(source):
            color = RgbColor.from_any(c)
            self._colors[i] = color
            if self._on_change is not None:
                self._on_change(i, color)
        self._dirty = True

    # Friendly aliases
    def set_colors(self, source: Sequence[RgbColor | tuple[int, int, int]]) -> None:
        self.update(source)

    def get_colors(self) -> list[RgbColor]:
        return self.copy()


# Back-compat names
MemoryPalette = Palette


def make_framebuffer(size: Size2D, bit_depth: BitDepth) -> FrameBuffer:
    """Allocate a managed (host-memory) framebuffer."""
    return FrameBuffer(size, bit_depth)
