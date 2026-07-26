#!/usr/bin/env python3
"""Basic VRAM scrolling pattern."""

from __future__ import annotations

import argparse
import sys

from rwt_rconsole import (
    CRT_4X3,
    BitDepth,
    ContentFit,
    DisplayConfig,
    PostEffect,
    Size2D,
    create_display,
    vga,
    video_math,
)


def draw_frame(display, frame: int) -> None:
    w, h = display.config.source_size
    span = display.buffer.view
    i = 0
    frame_base = frame * 3
    for y in range(h):
        v = (y + frame_base) & 0xFF
        for _x in range(w):
            span[i] = v
            i += 1
            v = (v + 2) & 0xFF


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="HelloRetro sample")
    p.add_argument("-c", "--crt", action="store_true", help="Enable CRT shader effect")
    p.add_argument("-f", "--fps", type=float, default=20.0, help="Target FPS")
    args = p.parse_args(argv)

    if args.fps <= 0:
        print("FPS must be positive", file=sys.stderr)
        return 1

    from rwt_rconsole.backends.metal import register as register_metal

    register_metal()

    effects = (PostEffect.CRT,) if args.crt else ()
    config = DisplayConfig(
        source_size=Size2D(320, 200),
        target_size=Size2D(320, 200),
        bit_depth=BitDepth.BPP8,
        content_fit=ContentFit.INTEGER_SCALE,
        aspect_ratio=CRT_4X3,
        title="HelloRetro",
        initial_scale=3,
        effects=effects,
    )

    with create_display(config) as display:
        display.palette.update(vga)
        frame = 0
        pres = video_math.presentation_size(config.target_size, config.aspect_ratio)
        print("Opening Metal window — Quit (⌘Q) or close button to exit.")
        print(
            f"Source {config.source_size.width}x{config.source_size.height} @ 8 bpp; "
            f"presentation {pres.width}x{pres.height}; CRT={args.crt}; "
            f"FPS={args.fps}; display≈{display.refresh_rate:.1f} Hz"
        )

        def on_frame(d):
            nonlocal frame
            draw_frame(d, frame)
            frame += 1
            return True  # present

        display.run(args.fps, on_frame)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
