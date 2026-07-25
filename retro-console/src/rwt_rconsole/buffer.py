"""Shared byte buffers with dirty tracking and buffer-protocol export."""

from __future__ import annotations

import ctypes
from typing import Any


class SharedByteBuffer:
    """C-contiguous uint8 storage with dirty tracking.

    Implements the buffer protocol so Python ``memoryview``, NumPy, and other
    C extensions can access the same memory via ``PyObject_GetBuffer``.

    Construction modes:

    * ``SharedByteBuffer(n)`` — owns a ``bytearray`` of length *n*.
    * ``SharedByteBuffer(n, address=ptr, owner=obj)`` — wraps an external
      native pointer (e.g. Metal shared buffer); *owner* keeps the native
      object alive for the lifetime of this view.
    """

    __slots__ = ("_length", "_data", "_address", "_owner", "_dirty", "_ctype_arr")

    def __init__(
        self,
        length: int,
        *,
        address: int | None = None,
        owner: Any = None,
    ) -> None:
        if length < 0:
            raise ValueError("Length must be non-negative.")
        self._length = length
        self._dirty = True
        self._owner = owner
        self._ctype_arr: Any = None

        if address is None:
            self._data: bytearray | None = bytearray(length)
            self._address: int | None = None
        else:
            if length > 0 and address == 0:
                raise ValueError("address must be non-null when length > 0")
            self._data = None
            self._address = int(address)
            if length > 0:
                self._ctype_arr = (ctypes.c_uint8 * length).from_address(self._address)

    def __len__(self) -> int:
        return self._length

    def __buffer__(self, flags: int) -> memoryview:
        # Export may lead to writes; mark dirty (pessimistic, safe for GPU upload).
        self._dirty = True
        if self._data is not None:
            return memoryview(self._data)
        if self._length == 0:
            return memoryview(bytearray())
        assert self._ctype_arr is not None
        return memoryview(self._ctype_arr).cast("B")

    @property
    def address(self) -> int:
        """Native pointer to the first byte (for ctypes / C consumers)."""
        if self._address is not None:
            return self._address
        assert self._data is not None
        if self._length == 0:
            return 0
        if self._ctype_arr is None:
            self._ctype_arr = (ctypes.c_uint8 * self._length).from_buffer(self._data)
        return ctypes.addressof(self._ctype_arr)

    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self) -> None:
        self._dirty = True

    def clear_dirty(self) -> None:
        self._dirty = False

    @property
    def view(self) -> memoryview:
        """Writable uint8 memoryview; marks the buffer dirty."""
        return memoryview(self)

    def fill(self, value: int = 0) -> None:
        """Fill all bytes with *value* and mark dirty."""
        v = value & 0xFF
        if self._data is not None:
            self._data[:] = bytes([v]) * self._length
            self._dirty = True
            return
        mv = self.view
        mv[:] = bytes([v]) * self._length
