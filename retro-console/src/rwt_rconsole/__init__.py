"""rwt_rconsole — memory-backed retro paletted display and streaming audio."""

from . import video_math
from .audio import (
    AudioChannels,
    AudioConfig,
    AudioPlaybackState,
    AudioSampleFormat,
    NullAudio,
    NullRetroAudio,
    as_float32,
    as_int16,
    as_int8,
    clear_audio_backend,
    create_audio,
    get_suggested_audio_config,
    register_audio_backend,
    suggested_audio_config,
)
from .buffer import SharedByteBuffer
from .display import (
    clear_display_backend,
    create_display,
    register_display_backend,
    should_present,
)
from .framebuffer import FrameBuffer
from .input import (
    InputContext,
    Key,
    MouseButton,
    MouseEventInfo,
    MouseMoveInfo,
    NullInputContext,
    RetroPoint,
)
from .memory import MemoryPalette, Palette, make_framebuffer
from .palettes import cga, ega, for_bit_depth, monochrome, vga
from .pixel_packing import get_pixel, set_pixel
from .types import (
    CRT_4X3,
    WIDE_16X9,
    BitDepth,
    ContentFit,
    DisplayConfig,
    FrameTickResult,
    PostEffect,
    RgbColor,
    Size2D,
)

__all__ = [
    # types
    "BitDepth",
    "ContentFit",
    "DisplayConfig",
    "FrameTickResult",
    "PostEffect",
    "RgbColor",
    "Size2D",
    "CRT_4X3",
    "WIDE_16X9",
    # buffers
    "SharedByteBuffer",
    "FrameBuffer",
    "Palette",
    "MemoryPalette",
    "make_framebuffer",
    "set_pixel",
    "get_pixel",
    # palettes
    "monochrome",
    "cga",
    "ega",
    "vga",
    "for_bit_depth",
    # display
    "create_display",
    "register_display_backend",
    "clear_display_backend",
    "should_present",
    "video_math",
    # input
    "Key",
    "MouseButton",
    "RetroPoint",
    "MouseEventInfo",
    "MouseMoveInfo",
    "InputContext",
    "NullInputContext",
    # audio
    "AudioChannels",
    "AudioConfig",
    "AudioPlaybackState",
    "AudioSampleFormat",
    "NullAudio",
    "NullRetroAudio",
    "as_float32",
    "as_int16",
    "as_int8",
    "create_audio",
    "suggested_audio_config",
    "get_suggested_audio_config",
    "register_audio_backend",
    "clear_audio_backend",
]

__version__ = "1.0"
