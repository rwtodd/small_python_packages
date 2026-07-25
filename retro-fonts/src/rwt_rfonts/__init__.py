"""rwt_rfonts — authentic EGA/VGA CP437 fonts and packed-pixel text blit."""

from .blit import put_char, put_char_fb, put_string, put_string_fb
from .cp437 import as_cp437, decode_cp437, encode_cp437
from .fonts import (
    CGA_8x8,
    DEFAULT_TEXT_FONT,
    EGA_8x14,
    Font,
    VGA_8x8,
    VGA_8x16,
    load_font,
    recommend_font,
)

__all__ = [
    "Font",
    "VGA_8x8",
    "CGA_8x8",
    "EGA_8x14",
    "VGA_8x16",
    "DEFAULT_TEXT_FONT",
    "recommend_font",
    "load_font",
    "encode_cp437",
    "decode_cp437",
    "as_cp437",
    "put_char",
    "put_string",
    "put_char_fb",
    "put_string_fb",
]

__version__ = "1.0"
