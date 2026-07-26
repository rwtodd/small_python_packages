"""Pure helpers for buffer sizes, scale factors, and coordinate mapping."""

from __future__ import annotations

from .input import RetroPoint
from .types import BitDepth, ContentFit, DisplayConfig, Size2D


def pitch(source: Size2D, bit_depth: BitDepth) -> int:
    """Bytes per source scanline for a tightly packed buffer (no padding)."""
    if bit_depth is BitDepth.BPP1:
        return source.width // 8
    if bit_depth is BitDepth.BPP4:
        return source.width // 2
    if bit_depth is BitDepth.BPP8:
        return source.width
    raise ValueError(f"Unsupported bit depth: {int(bit_depth)}")


def buffer_length(source: Size2D, bit_depth: BitDepth) -> int:
    """Total byte length of a packed source buffer."""
    return pitch(source, bit_depth) * source.height


def palette_length(bit_depth: BitDepth) -> int:
    """Number of palette entries for a bit depth (2 / 16 / 256)."""
    if bit_depth is BitDepth.BPP1:
        return 2
    if bit_depth is BitDepth.BPP4:
        return 16
    if bit_depth is BitDepth.BPP8:
        return 256
    raise ValueError(f"Unsupported bit depth: {int(bit_depth)}")


def scale_factors(source: Size2D, target: Size2D) -> tuple[int, int]:
    """Integer scale factors (target / source) on each axis."""
    if source.width <= 0 or source.height <= 0:
        raise ValueError("Source size must be positive.")
    if target.width % source.width != 0 or target.height % source.height != 0:
        raise ValueError(
            f"Target size {target.width}×{target.height} must be integer multiples "
            f"of source {source.width}×{source.height}."
        )
    return target.width // source.width, target.height // source.height


def presentation_size(target: Size2D, aspect_ratio: float) -> Size2D:
    """Square-pixel presentation size for a retro target at a physical aspect ratio.

    Keeps target width and derives height from aspect (320×200 @ 4:3 → 320×240).
    """
    if aspect_ratio <= 0.0:
        raise ValueError("Aspect ratio must be positive.")
    if target.width <= 0 or target.height <= 0:
        raise ValueError("Target size must be positive.")
    height = max(1, int(round(target.width / aspect_ratio)))
    return Size2D(target.width, height)


def initial_window_size(config: DisplayConfig) -> Size2D:
    """Initial window client size in square pixels (presentation × scale)."""
    pres = presentation_size(config.target_size, config.aspect_ratio)
    return Size2D(pres.width * config.initial_scale, pres.height * config.initial_scale)


def active_viewport(
    config: DisplayConfig,
    view_size: tuple[float, float],
) -> tuple[float, float, float, float] | None:
    """Return ``(active_w, active_h, offset_x, offset_y)`` for the retro viewport.

    Coordinates are in the same top-left origin space as *view_size*.
    Returns ``None`` if the view size is invalid.
    """
    view_width, view_height = view_size
    if view_width <= 0.0 or view_height <= 0.0:
        return None

    picture_aspect = max(config.aspect_ratio, 1e-6)
    view_aspect = view_width / view_height

    if config.content_fit is ContentFit.STRETCH:
        return view_width, view_height, 0.0, 0.0

    if config.content_fit is ContentFit.INTEGER_SCALE:
        # Largest integer multiple of the aspect-corrected presentation size
        # that fits in the window (prevents uneven pixel scaling / Moiré bands).
        pres = presentation_size(config.target_size, config.aspect_ratio)
        max_scale = max(
            1,
            min(int(view_width / float(pres.width)), int(view_height / float(pres.height))),
        )
        active_w = float(pres.width * max_scale)
        active_h = float(pres.height * max_scale)
        offset_x = (view_width - active_w) / 2.0
        offset_y = (view_height - active_h) / 2.0
        return active_w, active_h, offset_x, offset_y

    # LETTERBOX — largest uniform (possibly non-integer) scale that fits.
    if view_aspect > picture_aspect:
        active_w = view_height * picture_aspect
        offset_x = (view_width - active_w) / 2.0
        return active_w, view_height, offset_x, 0.0
    active_h = view_width / picture_aspect
    offset_y = (view_height - active_h) / 2.0
    return view_width, active_h, 0.0, offset_y


def screen_to_source(
    config: DisplayConfig,
    view_size: tuple[float, float],
    point: tuple[float, float],
) -> RetroPoint | None:
    """Map physical view coordinates (top-left origin) to retro source pixels.

    Returns ``None`` if the point is outside the active viewport
    (e.g. letterbox / integer-scale margins).
    """
    viewport = active_viewport(config, view_size)
    if viewport is None:
        return None

    active_w, active_h, offset_x, offset_y = viewport
    point_x, point_y = point

    if (
        point_x < offset_x
        or point_x >= offset_x + active_w
        or point_y < offset_y
        or point_y >= offset_y + active_h
    ):
        return None

    norm_x = (point_x - offset_x) / active_w
    norm_y = (point_y - offset_y) / active_h
    retro_x = min(
        config.source_size.width - 1,
        max(0, int(norm_x * float(config.source_size.width))),
    )
    retro_y = min(
        config.source_size.height - 1,
        max(0, int(norm_y * float(config.source_size.height))),
    )
    return RetroPoint(retro_x, retro_y)


# Back-compat alias
screen_to_source_coordinates = screen_to_source
