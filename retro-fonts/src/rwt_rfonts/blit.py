"""High-level text blit wrappers over the C ``_blit`` extension."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from . import _blit
from .cp437 import as_cp437
from .fonts import Font


@runtime_checkable
class FrameBufferLike(Protocol):
    """Duck type for ``rwt_rconsole.FrameBuffer`` (and similar)."""

    @property
    def size(self) -> Any: ...  # object with .width / .height

    @property
    def bit_depth(self) -> Any: ...  # int or IntEnum

    def mark_dirty(self) -> None: ...


def _size_wh(size: Any) -> tuple[int, int]:
    if isinstance(size, tuple) and len(size) == 2:
        return int(size[0]), int(size[1])
    return int(size.width), int(size.height)


def _bpp(bit_depth: Any) -> int:
    return int(bit_depth)


def _mark_dirty(buffer: Any) -> None:
    mark = getattr(buffer, "mark_dirty", None)
    if callable(mark):
        mark()
    # FrameBuffer may store dirty on .data
    data = getattr(buffer, "data", None)
    if data is not None:
        mark2 = getattr(data, "mark_dirty", None)
        if callable(mark2):
            mark2()


def put_char(
    font: Font,
    buffer: Any,
    *,
    size: Any,
    bit_depth: Any,
    x: int,
    y: int,
    code: int,
    fg: int,
    bg: int | None = None,
) -> None:
    """Blit one CP437 character at absolute pixel ``(x, y)``.

    *bg* ``None`` leaves background pixels undrawn (transparent).
    """
    put_string(
        font,
        buffer,
        size=size,
        bit_depth=bit_depth,
        x=x,
        y=y,
        text=bytes([code & 0xFF]),
        fg=fg,
        bg=bg,
        advance=False,
    )


def put_string(
    font: Font,
    buffer: Any,
    *,
    size: Any,
    bit_depth: Any,
    x: int,
    y: int,
    text: str | bytes | bytearray | memoryview,
    fg: int,
    bg: int | None = None,
    advance: bool = True,
) -> int:
    """Blit a string at absolute pixel ``(x, y)``.

    *text* is CP437 ``bytes`` or a ``str`` encoded as CP437.
    *bg* ``None`` is transparent.
    Returns the pixel *x* after the last glyph when *advance* is true;
    otherwise returns the original *x*.
    """
    w, h = _size_wh(size)
    bpp = _bpp(bit_depth)
    raw = as_cp437(text)
    bg_arg = -1 if bg is None else int(bg)

    # Prefer underlying storage if present (FrameBuffer.data) so we write
    # the same memory rconsole presents, but accept any buffer-protocol object.
    dst = getattr(buffer, "data", buffer)
    _blit.blit_string(
        dst,
        w,
        h,
        bpp,
        font.glyphs,
        font.height,
        int(x),
        int(y),
        raw,
        int(fg),
        bg_arg,
    )
    _mark_dirty(buffer)

    if advance:
        return int(x) + len(raw) * font.width
    return int(x)


def put_char_fb(
    font: Font,
    fb: FrameBufferLike,
    x: int,
    y: int,
    code: int,
    fg: int,
    bg: int | None = None,
) -> None:
    """``put_char`` using *fb.size* and *fb.bit_depth* from a FrameBuffer-like object."""
    put_char(
        font,
        fb,
        size=fb.size,
        bit_depth=fb.bit_depth,
        x=x,
        y=y,
        code=code,
        fg=fg,
        bg=bg,
    )


def put_string_fb(
    font: Font,
    fb: FrameBufferLike,
    x: int,
    y: int,
    text: str | bytes | bytearray | memoryview,
    fg: int,
    bg: int | None = None,
    *,
    advance: bool = True,
) -> int:
    """``put_string`` using *fb.size* and *fb.bit_depth* from a FrameBuffer-like object."""
    return put_string(
        font,
        fb,
        size=fb.size,
        bit_depth=fb.bit_depth,
        x=x,
        y=y,
        text=text,
        fg=fg,
        bg=bg,
        advance=advance,
    )
