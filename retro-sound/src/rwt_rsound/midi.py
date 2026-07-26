"""MIDI note helpers (notes/velocity only — not full MIDI control).

Maps MIDI note numbers to frequencies and chip-friendly periods. Instrument
setup, controllers, and SysEx are out of scope; use chip-specific APIs for
noise modes, FM operators, filters, etc.
"""

from __future__ import annotations

import math

from .nes_apu import NesApu
from .sn76496 import SN76496

A4_MIDI = 69
A4_HZ = 440.0


def midi_note_to_hz(note: int, *, a4_hz: float = A4_HZ) -> float:
    """Equal-tempered frequency for MIDI note number (A4 = 69 = 440 Hz)."""
    return float(a4_hz) * (2.0 ** ((int(note) - A4_MIDI) / 12.0))


def hz_to_midi_note(frequency_hz: float, *, a4_hz: float = A4_HZ) -> float:
    """Fractional MIDI note for a frequency (for display / rounding)."""
    if frequency_hz <= 0:
        raise ValueError("frequency_hz must be positive")
    return A4_MIDI + 12.0 * math.log2(float(frequency_hz) / float(a4_hz))


def velocity_to_sn_volume(velocity: int) -> int:
    """Map MIDI velocity 0..127 to SN76489 attenuation 15..0 (0=loud)."""
    v = max(0, min(127, int(velocity)))
    if v == 0:
        return 15
    # roughly linear in amplitude space → log atten steps
    level = v / 127.0
    # atten such that 10^(-0.1*a) ≈ level  → a ≈ -10*log10(level)
    atten = int(round(-10.0 * math.log10(level)))
    return max(0, min(15, atten))


def sn76496_note_on(
    chip: SN76496,
    channel: int,
    note: int,
    velocity: int = 100,
    *,
    a4_hz: float = A4_HZ,
) -> None:
    """Play a MIDI note on an SN76489 tone channel (0..2)."""
    if velocity <= 0:
        chip.note_off(channel)
        return
    hz = midi_note_to_hz(note, a4_hz=a4_hz)
    chip.note_on(channel, hz, volume=velocity_to_sn_volume(velocity))


def sn76496_note_off(chip: SN76496, channel: int) -> None:
    chip.note_off(channel)


def pc_speaker_note_on(chip: object, note: int, *, a4_hz: float = A4_HZ) -> None:
    """Gate on a PC speaker at a MIDI note frequency."""
    hz = midi_note_to_hz(note, a4_hz=a4_hz)
    set_f = getattr(chip, "set_frequency_hz")
    set_g = getattr(chip, "set_gate")
    set_f(hz)
    set_g(True)


def pc_speaker_note_off(chip: object) -> None:
    getattr(chip, "set_gate")(False)


def velocity_to_nes_volume(velocity: int) -> int:
    """Map MIDI velocity 0..127 to NES 4-bit volume 0..15."""
    v = max(0, min(127, int(velocity)))
    if v == 0:
        return 0
    return max(1, min(15, (v * 15) // 127))


def nes_pulse_note_on(
    chip: NesApu,
    channel: int,
    note: int,
    velocity: int = 100,
    *,
    duty: int = 2,
    a4_hz: float = A4_HZ,
    enable_mask: int | None = None,
) -> None:
    """Play a MIDI note on NES pulse channel 0 or 1."""
    if velocity <= 0:
        # mute via volume register while keeping enable
        base = 0x4000 if channel == 0 else 0x4004
        chip.write(base, 0x30)  # duty 0, const vol 0, halt
        return
    hz = midi_note_to_hz(note, a4_hz=a4_hz)
    chip.note_on_pulse(
        channel,
        hz,
        volume=velocity_to_nes_volume(velocity),
        duty=duty,
        enable_mask=enable_mask,
    )


def nes_pulse_note_off(chip: NesApu, channel: int) -> None:
    base = 0x4000 if channel == 0 else 0x4004
    chip.write(base, 0x30)
