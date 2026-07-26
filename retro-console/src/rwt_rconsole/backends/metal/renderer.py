"""Metal render pipeline for packed paletted VRAM."""

from __future__ import annotations

import importlib.resources
import struct
from pathlib import Path

from rwt_rconsole.types import ContentFit, DisplayConfig, PostEffect


def _load_shader_source() -> str:
    try:
        ref = importlib.resources.files("rwt_rconsole.backends.metal").joinpath("shaders.metal")
        return ref.read_text(encoding="utf-8")
    except Exception:
        path = Path(__file__).with_name("shaders.metal")
        return path.read_text(encoding="utf-8")


class MetalRenderer:
    def __init__(self, device, config: DisplayConfig, vram, palette) -> None:
        from Metal import (
            MTLClearColor,
            MTLLoadActionClear,
            MTLPixelFormatBGRA8Unorm,
            MTLPrimitiveTypeTriangle,
            MTLRenderPassDescriptor,
            MTLRenderPipelineDescriptor,
            MTLResourceStorageModeShared,
            MTLStoreActionStore,
            MTLCompileOptions,
        )

        self._device = device
        self._config = config
        self._vram = vram
        self._palette = palette

        self._queue = device.newCommandQueue()
        if self._queue is None:
            raise RuntimeError("Failed to create Metal command queue.")

        source = _load_shader_source()
        options = MTLCompileOptions.alloc().init()
        library, error = device.newLibraryWithSource_options_error_(source, options, None)
        if library is None:
            msg = str(error) if error is not None else "unknown error"
            raise RuntimeError(f"Failed to compile Metal shaders: {msg}")

        vertex = library.newFunctionWithName_("retro_vertex")
        fragment = library.newFunctionWithName_("retro_fragment")
        if vertex is None or fragment is None:
            raise RuntimeError("Missing retro_vertex or retro_fragment shader function.")

        desc = MTLRenderPipelineDescriptor.alloc().init()
        desc.setVertexFunction_(vertex)
        desc.setFragmentFunction_(fragment)
        desc.colorAttachments().objectAtIndexedSubscript_(0).setPixelFormat_(
            MTLPixelFormatBGRA8Unorm
        )
        pipeline, pipe_err = device.newRenderPipelineStateWithDescriptor_error_(desc, None)
        if pipeline is None:
            msg = str(pipe_err) if pipe_err is not None else "unknown error"
            raise RuntimeError(f"Failed to create render pipeline: {msg}")
        self._pipeline = pipeline

        # 32-byte uniforms: 6×uint32 + 2×float32
        self._uniform_buf = device.newBufferWithLength_options_(32, MTLResourceStorageModeShared)
        if self._uniform_buf is None:
            raise RuntimeError("Failed to create uniform buffer.")

        self._pass = MTLRenderPassDescriptor.renderPassDescriptor()
        color = self._pass.colorAttachments().objectAtIndexedSubscript_(0)
        color.setLoadAction_(MTLLoadActionClear)
        color.setStoreAction_(MTLStoreActionStore)
        color.setClearColor_(MTLClearColor(0.0, 0.0, 0.0, 1.0))
        self._color_attachment = color

        enable_crt = 1 if PostEffect.CRT in config.effects else 0
        self._uniforms = struct.pack(
            "<IIIIiffI",
            config.source_size.width,
            config.source_size.height,
            config.target_size.width,
            config.target_size.height,
            int(config.bit_depth),
            1.0,  # scaleX
            1.0,  # scaleY
            enable_crt,
        )
        self._write_uniforms(self._uniforms)
        self._last_drawable_w = -1.0
        self._last_drawable_h = -1.0
        self._enable_crt = enable_crt

    def _write_uniforms(self, data: bytes) -> None:
        from rwt_rconsole.backends.metal.surfaces import _wrap_mtl_buffer

        if not hasattr(self, "_uniform_owner"):
            addr, owner = _wrap_mtl_buffer(self._uniform_buf, 32)
            self._uniform_addr = addr
            self._uniform_owner = owner
        ctypes_buf = (ctypes.c_char * 32).from_address(self._uniform_addr)
        ctypes_buf[:32] = data

    def _update_scale(self, drawable_w: float, drawable_h: float) -> None:
        if drawable_w == self._last_drawable_w and drawable_h == self._last_drawable_h:
            return
        self._last_drawable_w = drawable_w
        self._last_drawable_h = drawable_h

        cfg = self._config
        picture_aspect = max(cfg.aspect_ratio, 1e-6)
        drawable_aspect = drawable_w / max(drawable_h, 1.0)

        if cfg.content_fit is ContentFit.STRETCH:
            scale_x, scale_y = 1.0, 1.0
        elif cfg.content_fit is ContentFit.INTEGER_SCALE:
            from rwt_rconsole.video_math import presentation_size

            pres = presentation_size(cfg.target_size, cfg.aspect_ratio)
            max_scale = max(
                1,
                min(int(drawable_w / float(pres.width)), int(drawable_h / float(pres.height))),
            )
            active_w = float(pres.width * max_scale)
            active_h = float(pres.height * max_scale)
            scale_x = active_w / drawable_w
            scale_y = active_h / drawable_h
        else:
            # LETTERBOX
            if drawable_aspect > picture_aspect:
                scale_x = picture_aspect / drawable_aspect
                scale_y = 1.0
            else:
                scale_x = 1.0
                scale_y = drawable_aspect / picture_aspect

        self._uniforms = struct.pack(
            "<IIIIiffI",
            cfg.source_size.width,
            cfg.source_size.height,
            cfg.target_size.width,
            cfg.target_size.height,
            int(cfg.bit_depth),
            scale_x,
            scale_y,
            self._enable_crt,
        )
        self._write_uniforms(self._uniforms)

    def present_layer(self, metal_layer) -> None:
        from Metal import MTLPrimitiveTypeTriangle

        drawable = metal_layer.nextDrawable()
        if drawable is None:
            return

        size = metal_layer.drawableSize()
        w = float(size.width)
        h = float(size.height)
        self._update_scale(w, h)

        texture = drawable.texture()
        self._color_attachment.setTexture_(texture)

        cmd = self._queue.commandBuffer()
        if cmd is None:
            return
        enc = cmd.renderCommandEncoderWithDescriptor_(self._pass)
        if enc is not None:
            enc.setRenderPipelineState_(self._pipeline)
            enc.setVertexBuffer_offset_atIndex_(self._uniform_buf, 0, 0)
            enc.setFragmentBuffer_offset_atIndex_(self._uniform_buf, 0, 0)
            enc.setFragmentBuffer_offset_atIndex_(self._vram.metal_buffer, 0, 1)
            enc.setFragmentBuffer_offset_atIndex_(self._palette.metal_buffer, 0, 2)
            enc.drawPrimitives_vertexStart_vertexCount_(MTLPrimitiveTypeTriangle, 0, 6)
            enc.endEncoding()

        cmd.presentDrawable_(drawable)
        cmd.commit()
        self._vram.clear_dirty()  # SharedByteBuffer / MetalVideoBuffer
        self._palette.clear_dirty()


# local import for ctypes in _write_uniforms
import ctypes  # noqa: E402
