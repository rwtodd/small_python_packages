#!/usr/bin/env python3
"""Demo: CP437 text, box-drawing, and graphical glyphs on rwt_rconsole.

Requires rwt_rconsole with the Metal backend (macOS)::

    uv sync --extra dev
    # peer install (extras use [brackets], not --extra):
    uv pip install -e "../retro-console[metal]"
    uv run python examples/text_demo.py --crt
"""

from __future__ import annotations

import argparse
import sys

from rwt_rfonts import VGA_8x16, encode_cp437, put_string_fb, recommend_font


def _frame_row(width_cells: int, left: int, fill: int, right: int) -> bytes:
    return bytes([left] + [fill] * (width_cells - 2) + [right])


def draw_static(display, font) -> None:
    """Paint a static CP437 showcase (box art + symbols)."""
    fb = display.buffer
    w, h = fb.size.width, fb.size.height
    cols, rows = font.cells_for(w, h)

    # Clear via opaque spaces
    x0, y0 = font.cell_to_pixel(0, 0)
    put_string_fb(font, fb, x0, y0, bytes([0x20]) * cols, fg=7, bg=0)
    for r in range(1, rows):
        x, y = font.cell_to_pixel(0, r)
        put_string_fb(font, fb, x, y, bytes([0x20]) * cols, fg=7, bg=0)

    # Outer double-line box (CP437)
    # ╔═╗ 0xC9 0xCD 0xBB
    # ║ ║ 0xBA     0xBA
    # ╚═╝ 0xC8 0xCD 0xBC
    box_w = min(cols, 48)
    box_h = min(rows - 2, 18)
    top = _frame_row(box_w, 0xC9, 0xCD, 0xBB)
    mid_empty = _frame_row(box_w, 0xBA, 0x20, 0xBA)
    bot = _frame_row(box_w, 0xC8, 0xCD, 0xBC)

    ox, oy = font.cell_to_pixel(1, 1)
    put_string_fb(font, fb, ox, oy, top, fg=11, bg=1)
    for r in range(1, box_h - 1):
        x, y = font.cell_to_pixel(1, 1 + r)
        put_string_fb(font, fb, x, y, mid_empty, fg=11, bg=1)
    x, y = font.cell_to_pixel(1, 1 + box_h - 1)
    put_string_fb(font, fb, x, y, bot, fg=11, bg=1)

    # Title (only CP437-safe characters; no em dash / multiplication sign)
    title = " rwt_rfonts - CP437 "
    tx, ty = font.cell_to_pixel(3, 1)
    put_string_fb(font, fb, tx, ty, title, fg=14, bg=1)

    # Content lines with mixed Unicode (encoded to CP437) and raw bytes.
    # Avoid U+2014 em dash and U+00D7 times - not in CP437 (encode to '?').
    lines: list[tuple[str | bytes, int]] = [
        ("IBM VGA 8x16  ·  authentic ROM glyphs", 15),
        ("", 7),
        ("Smileys: ☺ ☻    Music: ♪ ♫    Gender: ♂ ♀", 14),
        ("Cards:   ♠ ♣ ♥ ♦    Solar: ☼     Bullet: •", 12),
        ("Math:    ± ∞ ∩ ≡ ≈ √ ⁿ ²", 10),
        ("", 7),
        ("Blocks:  ░ ▒ ▓ █ ▄ ▌ ▐ ▀", 7),
        ("Single:  ┌─┬─┐  │ │ │  └─┴─┘  ├─┤", 15),
        ("Double:  ╔═╦═╗  ║ ║ ║  ╚═╩═╝  ╠═╣", 11),
        ("Mixed:   ╓─╥─╖  ╟─╫─╢  ╙─╨─╜", 13),
        ("", 7),
        (bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x0E, 0x0F, 0x10, 0x11, 0x1E, 0x1F]), 14),
        ("(low controls / arrows as in DOS)", 8),
    ]

    for i, (line, color) in enumerate(lines):
        row = 3 + i
        if row >= 1 + box_h - 1:
            break
        x, y = font.cell_to_pixel(3, row)
        text = line if isinstance(line, bytes) else encode_cp437(line)
        # clip to inner width
        max_chars = box_w - 4
        text = text[:max_chars]
        put_string_fb(font, fb, x, y, text, fg=color, bg=1)

    # Footer outside the box
    foot = f"Mode {w}x{h}  cells {cols}x{rows}  font {font.name}"
    fx, fy = font.cell_to_pixel(1, min(rows - 1, 1 + box_h + 1))
    put_string_fb(font, fb, fx, fy, foot[: cols - 1], fg=7, bg=None)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="CP437 font demo for rwt_rconsole")
    p.add_argument("-c", "--crt", action="store_true", help="Enable CRT shader")
    p.add_argument("-f", "--fps", type=float, default=30.0)
    p.add_argument(
        "--mode",
        choices=("640x400", "640x480", "320x200", "320x240"),
        default="640x400",
        help="Source resolution (default VGA text-friendly 640x400)",
    )
    args = p.parse_args(argv)

    try:
        from rwt_rconsole import (
            CRT_4X3,
            BitDepth,
            ContentFit,
            DisplayConfig,
            PostEffect,
            Size2D,
            create_display,
            vga,
        )
        from rwt_rconsole.backends.metal import register as register_metal
    except ImportError as e:
        print(
            "rwt_rconsole (with Metal) is required for this demo:\n"
            '  uv pip install -e "../retro-console[metal]"\n'
            f"({e})",
            file=sys.stderr,
        )
        return 1

    register_metal()
    sw, sh = (int(x) for x in args.mode.split("x"))
    font = recommend_font(sw, sh)
    # Prefer 8x16 on 640x400 for classic 80x25
    if args.mode in ("640x400", "640x480"):
        font = VGA_8x16

    effects = (PostEffect.CRT,) if args.crt else ()
    config = DisplayConfig(
        source_size=Size2D(sw, sh),
        target_size=Size2D(sw, sh),
        bit_depth=BitDepth.BPP8,
        content_fit=ContentFit.LETTERBOX,
        aspect_ratio=CRT_4X3,
        title="rwt_rfonts demo",
        initial_scale=2 if sw >= 640 else 3,
        effects=effects,
    )

    with create_display(config) as display:
        display.palette.update(vga)
        drawn = False

        def on_frame(d):
            nonlocal drawn
            if not drawn:
                draw_static(d, font)
                drawn = True
            return True

        print(
            f"Font {font.name}; {sw}x{sh}; "
            f"cells {font.cells_for(sw, sh)}; CRT={args.crt}"
        )
        print("Quit (⌘Q) or close the window to exit.")
        display.run(args.fps, on_frame)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
