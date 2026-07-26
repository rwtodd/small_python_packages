"""PCM buffer helpers for offline render and rwt_rconsole callbacks."""

from __future__ import annotations

from typing import Any


def as_float32_mono(destination: Any) -> memoryview:
    """Return a writable float32 view of *destination* (bytes/bytearray/mv)."""
    mv = memoryview(destination)
    if mv.format == "f" and mv.ndim == 1:
        return mv if not mv.readonly else mv
    if mv.readonly:
        raise BufferError("destination must be writable")
    # raw bytes → float32
    if mv.format == "B" or mv.itemsize == 1:
        if len(mv) % 4 != 0:
            raise ValueError("byte length must be a multiple of 4")
        return mv.cast("f")
    if mv.format == "f":
        return mv.cast("f") if mv.ndim != 1 else mv
    return mv.cast("f")


def render_mono_to_stereo(
    chip: Any,
    destination: Any,
    *,
    channels: int = 2,
) -> None:
    """Render a mono chip into an interleaved float32 buffer.

    For stereo (*channels* == 2), each mono sample is duplicated L/R.
    For mono (*channels* == 1), samples are written directly.
    """
    dest = as_float32_mono(destination)
    n_dest = len(dest)
    if channels < 1:
        raise ValueError("channels must be >= 1")
    if n_dest % channels != 0:
        raise ValueError("destination length must be divisible by channels")
    frames = n_dest // channels
    if channels == 1:
        chip.render_into(dest)
        return
    mono = chip.render(frames)
    for i in range(frames):
        s = float(mono[i])
        base = i * channels
        for c in range(channels):
            dest[base + c] = s
