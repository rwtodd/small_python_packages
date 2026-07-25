# Font provenance

Binary glyph dumps embedded in this package are **IBM EGA/VGA character-generator
fonts** for Code Page 437 (CP437), in the classic ROM layout:

- 256 glyphs, codes `0x00`–`0xFF`
- Width 8 pixels; each scanline is one byte; **MSB is the leftmost pixel**
- Total size = `256 × height` bytes

## Files

| File | Size | Source (spacerace/romfont) | MD5 |
|------|------|----------------------------|-----|
| `ibm_vga_8x8.bin` | 2048 | `font-bin/IBM_VGA_8x8.bin` | `36addababf8830d29e7502e7a4d4d9f8` |
| `ibm_ega_8x14.bin` | 3584 | `font-bin/ibm-ega__8x14.bin` | `8bcbaf14d1c2729dbbbd486d0929f98c` |
| `ibm_vga_8x16.bin` | 4096 | `font-bin/IBM_VGA_8x16.bin` | `10c3d174722de153243d60a06d29865a` |

Collection: [spacerace/romfont](https://github.com/spacerace/romfont) — fonts
extracted from BIOS and VGA/EGA ROMs.

Notes:

- `ibm-ega__8x14.bin` is **byte-identical** to `IBM_VGA_8x14.bin` (IBM reused the
  EGA 8×14 set on VGA).
- SeaBIOS ships matching 8×8 / 8×14 glyphs (often cited as matching
  `fntcol16` VGA-ROM.F08 / F14).

## License note

These bitmaps originate from IBM (and clone) video ROMs. Redistribution is common
in emulators and open-source BIOS projects, but the legal status of the original
ROM artwork is not clear-cut public domain. This package embeds them for
historical authenticity when rendering CP437 text. Replace with a clean-room or
explicitly licensed lookalike if your distribution requirements demand it; the
API does not depend on a particular binary.
