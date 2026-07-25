"""Code Page 437 encode/decode helpers.

Python's stdlib ``cp437`` codec leaves bytes ``0x00``–``0x1F`` and ``0x7F`` as
C0 controls (not the DOS glyph forms). This module uses the full **IBM CP437**
Unicode mapping so box-drawing, smileys, card suits, arrows, etc. round-trip.
"""

from __future__ import annotations

# Full 256-entry Unicode mapping for IBM CP437 (glyph forms for C0 / DEL).
# Index = byte value. Matches common DOS / VGA documentation.
_CP437_CHARS: str = (
    "\u0000"  # 00  null (no glyph / blank)
    "\u263a"  # 01  ☺
    "\u263b"  # 02  ☻
    "\u2665"  # 03  ♥
    "\u2666"  # 04  ♦
    "\u2663"  # 05  ♣
    "\u2660"  # 06  ♠
    "\u2022"  # 07  •
    "\u25d8"  # 08  ◘
    "\u25cb"  # 09  ○
    "\u25d9"  # 0A  ◙
    "\u2642"  # 0B  ♂
    "\u2640"  # 0C  ♀
    "\u266a"  # 0D  ♪
    "\u266b"  # 0E  ♫
    "\u263c"  # 0F  ☼
    "\u25ba"  # 10  ►
    "\u25c4"  # 11  ◄
    "\u2195"  # 12  ↕
    "\u203c"  # 13  ‼
    "\u00b6"  # 14  ¶
    "\u00a7"  # 15  §
    "\u25ac"  # 16  ▬
    "\u21a8"  # 17  ↨
    "\u2191"  # 18  ↑
    "\u2193"  # 19  ↓
    "\u2192"  # 1A  →
    "\u2190"  # 1B  ←
    "\u221f"  # 1C  ∟
    "\u2194"  # 1D  ↔
    "\u25b2"  # 1E  ▲
    "\u25bc"  # 1F  ▼
    # 20–7E ASCII
    " !\"#$%&'()*+,-./0123456789:;<=>?"
    "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_"
    "`abcdefghijklmnopqrstuvwxyz{|}~"
    "\u2302"  # 7F  ⌂
    # 80–FF
    "\u00c7\u00fc\u00e9\u00e2\u00e4\u00e0\u00e5\u00e7"
    "\u00ea\u00eb\u00e8\u00ef\u00ee\u00ec\u00c4\u00c5"
    "\u00c9\u00e6\u00c6\u00f4\u00f6\u00f2\u00fb\u00f9"
    "\u00ff\u00d6\u00dc\u00a2\u00a3\u00a5\u20a7\u0192"
    "\u00e1\u00ed\u00f3\u00fa\u00f1\u00d1\u00aa\u00ba"
    "\u00bf\u2310\u00ac\u00bd\u00bc\u00a1\u00ab\u00bb"
    "\u2591\u2592\u2593\u2502\u2524\u2561\u2562\u2556"
    "\u2555\u2563\u2551\u2557\u255d\u255c\u255b\u2510"
    "\u2514\u2534\u252c\u251c\u2500\u253c\u255e\u255f"
    "\u255a\u2554\u2569\u2566\u2560\u2550\u256c\u2567"
    "\u2568\u2564\u2565\u2559\u2558\u2552\u2553\u256b"
    "\u256a\u2518\u250c\u2588\u2584\u258c\u2590\u2580"
    "\u03b1\u00df\u0393\u03c0\u03a3\u03c3\u00b5\u03c4"
    "\u03a6\u0398\u03a9\u03b4\u221e\u03c6\u03b5\u2229"
    "\u2261\u00b1\u2265\u2264\u2320\u2321\u00f7\u2248"
    "\u00b0\u2219\u00b7\u221a\u207f\u00b2\u25a0\u00a0"
)

assert len(_CP437_CHARS) == 256

# Prefer first byte when Unicode would map to multiple (NUL stays 0).
_ENCODE: dict[str, int] = {}
for _i, _ch in enumerate(_CP437_CHARS):
    if _ch not in _ENCODE:
        _ENCODE[_ch] = _i

# Also accept C0 control codepoints as themselves (so b"\x03" paths and chr(3) work).
for _i in range(0x20):
    _ENCODE.setdefault(chr(_i), _i)
_ENCODE.setdefault("\x7f", 0x7F)


def encode_cp437(s: str, *, errors: str = "replace") -> bytes:
    """Encode *s* as CP437 bytes using the full IBM glyph map.

    *errors*: ``"strict"`` | ``"replace"`` (→ ``?`` / 0x3F) | ``"ignore"``.
    """
    out = bytearray(len(s))
    j = 0
    for ch in s:
        b = _ENCODE.get(ch)
        if b is None:
            if errors == "strict":
                raise UnicodeEncodeError(
                    "cp437",
                    s,
                    j,
                    j + 1,
                    f"character {ch!r} (U+{ord(ch):04X}) is not in CP437",
                )
            if errors == "ignore":
                continue
            # replace
            b = 0x3F
        out[j] = b
        j += 1
    return bytes(out[:j])


def decode_cp437(b: bytes | bytearray | memoryview, *, errors: str = "strict") -> str:
    """Decode CP437 bytes to Unicode (DOS glyph forms for 0x00–0x1F / 0x7F)."""
    if isinstance(b, memoryview):
        b = b.tobytes()
    data = bytes(b)
    try:
        return "".join(_CP437_CHARS[x] for x in data)
    except IndexError:
        # unreachable for uint8
        if errors == "strict":
            raise
        return "".join(_CP437_CHARS[x] if x < 256 else "?" for x in data)


def as_cp437(text: str | bytes | bytearray | memoryview) -> bytes:
    """Normalize *text* to CP437 ``bytes``.

    * ``bytes`` / ``bytearray`` / ``memoryview`` are raw CP437 codes.
    * ``str`` is encoded with :func:`encode_cp437`.
    """
    if isinstance(text, str):
        return encode_cp437(text)
    if isinstance(text, memoryview):
        return text.tobytes()
    return bytes(text)
