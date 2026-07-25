#!/usr/bin/env python3
"""Keyboard movement + mouse drawing."""

from __future__ import annotations

import argparse
import sys

from rwt_rconsole import (
    CRT_4X3,
    BitDepth,
    ContentFit,
    DisplayConfig,
    Key,
    MouseButton,
    PostEffect,
    Size2D,
    create_display,
    vga,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="InputDemo sample")
    p.add_argument("-c", "--crt", action="store_true", help="Enable CRT shader effect")
    p.add_argument("-f", "--fps", type=float, default=60.0, help="Target FPS")
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
        content_fit=ContentFit.LETTERBOX,
        aspect_ratio=CRT_4X3,
        title="InputDemo",
        initial_scale=3,
        effects=effects,
    )

    px, py = 160, 100

    with create_display(config) as display:
        display.palette.update(vga)
        display.buffer.fill(0)

        def on_frame(d):
            nonlocal px, py
            inp = d.input
            w, h = config.source_size
            if inp.is_key_down(Key.W) or inp.is_key_down(Key.UP):
                py = max(0, py - 1)
            if inp.is_key_down(Key.S) or inp.is_key_down(Key.DOWN):
                py = min(h - 1, py + 1)
            if inp.is_key_down(Key.A) or inp.is_key_down(Key.LEFT):
                px = max(0, px - 1)
            if inp.is_key_down(Key.D) or inp.is_key_down(Key.RIGHT):
                px = min(w - 1, px + 1)

            d.buffer[px, py] = 14

            pos = inp.mouse_position
            if pos is not None and inp.is_mouse_button_down(MouseButton.LEFT):
                d.buffer[pos.x, pos.y] = 12

            return True

        print(
            f"WASD/arrows move yellow pixel; left-click draws red. "
            f"CRT={args.crt}; FPS={args.fps}. Close to exit."
        )
        display.run(args.fps, on_frame)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
