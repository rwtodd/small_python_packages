#!/usr/bin/env python3
"""Real-time sine tone with reverb."""

from __future__ import annotations

import math
import time

from rwt_rconsole import AudioConfig, as_float32, create_audio, suggested_audio_config


def main() -> int:
    from rwt_rconsole.backends.apple_audio import register as register_audio

    register_audio()

    base = suggested_audio_config()
    cfg = AudioConfig(
        sample_rate=base.sample_rate,
        channels=base.channels,
        format=base.format,
        reverb=64,
    )

    phase = 0.0
    frequency = 440.0

    def callback(destination: memoryview) -> None:
        nonlocal phase
        floats = as_float32(destination)
        nframes = len(floats) // int(cfg.channels)
        phase_inc = (2.0 * math.pi * frequency) / float(cfg.sample_rate)
        for i in range(nframes):
            sample = math.sin(phase) * 0.2
            phase += phase_inc
            if phase >= 2.0 * math.pi:
                phase -= 2.0 * math.pi
            floats[i * 2] = sample
            floats[i * 2 + 1] = sample

    with create_audio(cfg, callback) as audio:
        print(f"Playing A4 sine @ {cfg.sample_rate} Hz stereo, reverb={cfg.reverb}")
        print("Ctrl+C to stop.")
        audio.play()
        try:
            while True:
                if audio.last_error is not None:
                    print("Audio error:", audio.last_error)
                    break
                time.sleep(0.25)
        except KeyboardInterrupt:
            print("\nStopping.")
        audio.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
