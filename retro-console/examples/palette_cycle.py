#!/usr/bin/env python3
"""4 bpp palette animation."""

from __future__ import annotations

import argparse
import math
import sys

from rwt_rconsole import (
    CRT_4X3,
    BitDepth,
    ContentFit,
    DisplayConfig,
    PostEffect,
    Size2D,
    create_display,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="PaletteCycle sample")
    p.add_argument("-c", "--crt", action="store_true", help="Enable CRT shader effect")
    p.add_argument("-f", "--fps", type=float, default=30.0, help="Target FPS")
    args = p.parse_args(argv)

    if args.fps <= 0:
        print("FPS must be positive", file=sys.stderr)
        return 1

    from rwt_rconsole.backends.metal import register as register_metal

    register_metal()

    effects = (PostEffect.CRT,) if args.crt else ()
    config = DisplayConfig(
        source_size=Size2D(160, 200),
        target_size=Size2D(320, 200),
        bit_depth=BitDepth.BPP4,
        content_fit=ContentFit.INTEGER_SCALE,
        aspect_ratio=CRT_4X3,
        title="PaletteCycle",
        initial_scale=3,
        effects=effects,
    )

    with create_display(config) as display:
        w, h = config.source_size
        for y in range(h):
            for x in range(w):
                display.buffer[x, y] = (x + y) % 16

        frame = 0

        def on_frame(d):
            nonlocal frame
            for i in range(16):
                phase = frame * 0.08 + i * 0.4
                r = int(127 + 127 * math.sin(phase)) & 255
                g = int(127 + 127 * math.sin(phase + 2.0)) & 255
                b = int(127 + 127 * math.sin(phase + 4.0)) & 255
                d.palette[i] = (r, g, b)
            frame += 1
            return True

        print(f"Palette cycling — CRT={args.crt}; FPS={args.fps}. Close window to exit.")
        display.run(args.fps, on_frame)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
