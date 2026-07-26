"""Core configuration and value types for retro displays."""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum, IntEnum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class BitDepth(IntEnum):
    """Bits per pixel of the packed source framebuffer (not planar)."""

    BPP1 = 1
    BPP4 = 4
    BPP8 = 8


class ContentFit(Enum):
    """How the target image maps into a freely resizable window (nearest-neighbor)."""

    LETTERBOX = auto()  # largest uniform scale that fits; unused area is black
    INTEGER_SCALE = auto()  # largest integer scale (1×, 2×, …); avoids uneven pixel bands
    STRETCH = auto()  # fill the client area (may be non-uniform)


class PostEffect(Enum):
    """Pre-defined post-processing shader effects."""

    CRT = auto()


class FrameTickResult(Enum):
    """Optional explicit return value from a frame callback."""

    PRESENT = auto()
    SKIP = auto()


# Common aspect ratios (width ÷ height).
CRT_4X3: float = 4.0 / 3.0
WIDE_16X9: float = 16.0 / 9.0


@dataclass(frozen=True, slots=True)
class Size2D:
    """Logical size in pixels. Unpacks as ``width, height``."""

    width: int
    height: int

    def __iter__(self) -> Iterator[int]:
        yield self.width
        yield self.height


@dataclass(frozen=True, slots=True)
class RgbColor:
    """8-bit RGB palette entry (no alpha)."""

    r: int
    g: int
    b: int

    def __post_init__(self) -> None:
        for name, v in (("r", self.r), ("g", self.g), ("b", self.b)):
            if not isinstance(v, int) or not 0 <= v <= 255:
                raise ValueError(f"RgbColor.{name} must be an int 0..255, got {v!r}")

    @classmethod
    def from_any(cls, value: RgbColor | tuple[int, int, int]) -> RgbColor:
        if isinstance(value, RgbColor):
            return value
        r, g, b = value
        return cls(r, g, b)


@dataclass(frozen=True, slots=True)
class DisplayConfig:
    """Configuration for a retro display window and framebuffer.

    Validated on construction (raises ``ValueError`` if invalid).
    """

    source_size: Size2D
    target_size: Size2D
    bit_depth: BitDepth = BitDepth.BPP8
    content_fit: ContentFit = ContentFit.LETTERBOX
    aspect_ratio: float = CRT_4X3
    title: str = "RetroConsole"
    initial_scale: int = 3
    effects: tuple[PostEffect, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        # Local import avoids circular dependency with video_math helpers' pure checks.
        _validate_display_config(self)


def _validate_display_config(config: DisplayConfig) -> None:
    """Raise ValueError if *config* is invalid."""
    if config.bit_depth not in (BitDepth.BPP1, BitDepth.BPP4, BitDepth.BPP8):
        raise ValueError(f"Unsupported bit depth: {int(config.bit_depth)}.")
    if config.source_size.width <= 0 or config.source_size.height <= 0:
        raise ValueError("Source size must be positive on both axes.")
    if config.target_size.width <= 0 or config.target_size.height <= 0:
        raise ValueError("Target size must be positive on both axes.")
    if config.initial_scale < 1:
        raise ValueError("initial_scale must be >= 1.")
    if (
        config.aspect_ratio <= 0.0
        or math.isnan(config.aspect_ratio)
        or math.isinf(config.aspect_ratio)
    ):
        raise ValueError("aspect_ratio must be a finite positive number (e.g. 4/3).")
    src = config.source_size
    if config.bit_depth is BitDepth.BPP1 and src.width % 8 != 0:
        raise ValueError(f"1 bpp requires width divisible by 8 (got {src.width}).")
    if config.bit_depth is BitDepth.BPP4 and src.width % 2 != 0:
        raise ValueError(f"4 bpp requires even width (got {src.width}).")
    tgt = config.target_size
    if tgt.width % src.width != 0 or tgt.height % src.height != 0:
        raise ValueError(
            f"Target size {tgt.width}×{tgt.height} must be integer multiples "
            f"of source {src.width}×{src.height}."
        )
    if not config.title or not str(config.title).strip():
        raise ValueError("title must be non-empty.")
