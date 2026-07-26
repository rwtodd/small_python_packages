"""PC Speaker core tests."""

from __future__ import annotations

import math
import struct

import pytest

from rwt_rsound import PIT_CLOCK_HZ, PCSpeaker, Waveform, midi_note_to_hz


def _rms(samples: memoryview) -> float:
    n = len(samples)
    if n == 0:
        return 0.0
    acc = sum(float(s) * float(s) for s in samples)
    return math.sqrt(acc / n)


def test_silent_when_gate_off() -> None:
    spk = PCSpeaker(sample_rate=8000)
    spk.set_frequency_hz(440.0)
    spk.set_gate(False)
    buf = spk.render(800)
    assert all(s == 0.0 for s in buf)


def test_beep_has_energy() -> None:
    spk = PCSpeaker(sample_rate=8000, amplitude=0.5)
    spk.beep(440.0)
    buf = spk.render(800)
    assert _rms(buf) > 0.1


def test_pit_divisor() -> None:
    spk = PCSpeaker(sample_rate=44100)
    div = 0x0533
    spk.set_pit_divisor(div)
    expected = PIT_CLOCK_HZ / div
    assert spk.frequency_hz == pytest.approx(expected, rel=1e-9)


def test_waveform_square_vs_sine_differ() -> None:
    sr = 8000
    n = 2000

    sq = PCSpeaker(sample_rate=sr, amplitude=0.5)
    sq.beep(220.0)
    sq.set_waveform(Waveform.SQUARE)
    a = list(sq.render(n))

    si = PCSpeaker(sample_rate=sr, amplitude=0.5)
    si.beep(220.0)
    si.set_waveform(Waveform.SINE)
    b = list(si.render(n))

    # not identical waveforms
    assert a != b
    assert _rms(memoryview(struct.pack(f"{n}f", *b)).cast("f")) > 0.05


def test_write_bus() -> None:
    spk = PCSpeaker(sample_rate=8000)
    spk.write(0, 1000)
    spk.write(1, 1)
    assert spk.gate is True
    assert spk.frequency_hz == pytest.approx(PIT_CLOCK_HZ / 1000)


def test_midi_helper_freq() -> None:
    assert midi_note_to_hz(69) == pytest.approx(440.0)
    assert midi_note_to_hz(60) == pytest.approx(261.6255, rel=1e-4)


def test_protocol_attrs() -> None:
    spk = PCSpeaker()
    assert spk.name == "pc_speaker"
    assert spk.channels_out == 1
    spk.reset()
    assert spk.gate is False
