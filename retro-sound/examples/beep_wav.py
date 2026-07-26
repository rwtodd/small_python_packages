#!/usr/bin/env python3
"""Render a short PC Speaker beep and Tandy chord to WAV files (stdlib only)."""

from __future__ import annotations

import struct
import wave
from pathlib import Path

from rwt_rsound import NesApu, PCSpeaker, Waveform, tandy_sound


def write_wav(path: Path, samples: memoryview, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        # float32 -1..1 → int16
        frames = bytearray()
        for s in samples:
            v = max(-1.0, min(1.0, float(s)))
            frames.extend(struct.pack("<h", int(v * 32767.0)))
        w.writeframes(frames)


def main() -> int:
    out = Path(__file__).resolve().parent / "out"
    sr = 44100

    spk = PCSpeaker(sample_rate=sr, amplitude=0.3)
    spk.beep(880.0)
    write_wav(out / "pc_speaker_a5.wav", spk.render(sr // 2), sr)

    spk.reset()
    spk.set_waveform(Waveform.TRIANGLE)
    spk.beep(440.0)
    write_wav(out / "pc_speaker_triangle.wav", spk.render(sr // 2), sr)

    psg = tandy_sound(sample_rate=sr, master_gain=0.2)
    psg.note_on(0, 262.0, volume=1)
    psg.note_on(1, 330.0, volume=2)
    psg.note_on(2, 392.0, volume=3)
    write_wav(out / "tandy_chord.wav", psg.render(sr), sr)

    nes = NesApu(sample_rate=sr, master_gain=0.5)
    nes.note_on_pulse(0, 523.25, volume=10, duty=2, enable_mask=0x05)
    nes.enable_channels(pulse1=True, triangle=True)
    nes.set_pulse(0, frequency_hz=523.25, volume=10, duty=2)
    nes.set_triangle(frequency_hz=261.63, linear=0x7F, control=True)
    write_wav(out / "nes_pulse_tri.wav", nes.render(sr), sr)

    print(f"Wrote WAVs under {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
