"""Metal shared VRAM and palette buffers."""

from __future__ import annotations

import ctypes

from rwt_rconsole.buffer import SharedByteBuffer
from rwt_rconsole.memory import Palette
from rwt_rconsole.types import RgbColor


def _wrap_mtl_buffer(mtl_buffer, length: int) -> tuple[int, object]:
    """Return (address, owner_tuple) for a Metal shared buffer's CPU mapping."""
    contents = mtl_buffer.contents()
    if contents is None:
        raise RuntimeError("MTLBuffer.contents() returned None")
    if length == 0:
        return 0, (mtl_buffer, contents)
    # PyObjC returns objc.varlist; as_buffer(n) yields a writable memoryview.
    mv = contents.as_buffer(length)
    arr = (ctypes.c_uint8 * length).from_buffer(mv)
    addr = ctypes.addressof(arr)
    # Keep mtl_buffer, varlist, memoryview, and ctypes array alive together.
    return addr, (mtl_buffer, contents, mv, arr)


class MetalVideoBuffer(SharedByteBuffer):
    """VRAM backed by a Metal shared buffer (CPU/GPU unified memory)."""

    def __init__(self, device, length: int) -> None:
        from Metal import MTLResourceStorageModeShared

        mtl_buf = device.newBufferWithLength_options_(length, MTLResourceStorageModeShared)
        if mtl_buf is None:
            raise RuntimeError("Failed to create shared Metal VRAM buffer.")
        addr, owner = _wrap_mtl_buffer(mtl_buf, length)
        super().__init__(length, address=addr, owner=owner)
        self.metal_buffer = mtl_buf


class MetalPalette(Palette):
    """Palette with a Metal float4 RGBA shadow buffer for the fragment shader."""

    def __init__(self, device, count: int, initial) -> None:
        from Metal import MTLResourceStorageModeShared

        byte_length = count * 16
        mtl_buf = device.newBufferWithLength_options_(byte_length, MTLResourceStorageModeShared)
        if mtl_buf is None:
            raise RuntimeError("Failed to create shared Metal palette buffer.")
        self.metal_buffer = mtl_buf
        addr, owner = _wrap_mtl_buffer(mtl_buf, byte_length)
        self._gpu_owner = owner
        self._gpu_addr = addr
        self._gpu_len = byte_length

        def on_change(index: int, color: RgbColor) -> None:
            self._write_entry(index, color)

        super().__init__(count, initial, on_change=on_change)
        for i, c in enumerate(self):
            self._write_entry(i, c)

    def _write_entry(self, index: int, color: RgbColor) -> None:
        offset = self._gpu_addr + index * 16
        floats = (ctypes.c_float * 4).from_address(offset)
        floats[0] = color.r / 255.0
        floats[1] = color.g / 255.0
        floats[2] = color.b / 255.0
        floats[3] = 1.0
