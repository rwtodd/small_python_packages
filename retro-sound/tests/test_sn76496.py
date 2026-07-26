"""SN76489-family (Tandy / Sega) tests."""

from __future__ import annotations

import math

import pytest

from rwt_rsound import (
    SN76496,
    SN76496Variant,
    Waveform,
    sega_psg,
    sn76496_note_on,
    sn76496_note_off,
    tandy_sound,
)


def _rms(samples: memoryview) -> float:
    n = len(samples)
    if n == 0:
        return 0.0
    acc = sum(float(s) * float(s) for s in samples)
    return math.sqrt(acc / n)


def test_factories_variants() -> None:
    t = tandy_sound(sample_rate=8000)
    s = sega_psg(sample_rate=8000)
    assert t.variant is SN76496Variant.TANDY
    assert s.variant is SN76496Variant.SEGA
    assert "tandy" in t.name
    assert "sega" in s.name


def test_tone_has_energy() -> None:
    psg = tandy_sound(sample_rate=8000, master_gain=0.5)
    psg.note_on(0, 440.0, volume=0)
    buf = psg.render(2000)
    assert _rms(buf) > 0.05


def test_muted_is_quiet() -> None:
    psg = tandy_sound(sample_rate=8000)
    psg.set_tone(0, frequency_hz=440.0, volume=15)
    buf = psg.render(1000)
    assert _rms(buf) < 1e-6


def test_frequency_from_period() -> None:
    psg = tandy_sound(sample_rate=44100, clock_hz=3_579_545.0)
    psg.set_tone(0, period=0x100, volume=0)
    # f = clock / (32 * period)
    expected = 3_579_545.0 / (32.0 * 0x100)
    assert psg.tone_frequency(0) == pytest.approx(expected)


def test_register_write_period() -> None:
    psg = tandy_sound(sample_rate=8000)
    psg.write_tone_period(1, 0x123)
    psg.write_volume(1, 0)
    assert psg.tone_frequency(1) == pytest.approx(
        psg.clock_hz / (32.0 * 0x123), rel=1e-6
    )
    assert _rms(psg.render(1500)) > 0.01


def test_noise_has_energy() -> None:
    psg = tandy_sound(sample_rate=8000, master_gain=0.5)
    psg.set_noise(white=True, rate=0, volume=0)
    buf = psg.render(4000)
    assert _rms(buf) > 0.01


def test_tandy_and_sega_noise_differ() -> None:
    """Different LFSR profiles should not produce identical streams."""
    n = 3000
    t = tandy_sound(sample_rate=8000, master_gain=0.5)
    s = sega_psg(sample_rate=8000, master_gain=0.5)
    t.set_noise(white=True, rate=1, volume=0)
    s.set_noise(white=True, rate=1, volume=0)
    a = list(t.render(n))
    b = list(s.render(n))
    assert a != b


def test_tone_waveform_extension() -> None:
    psg = tandy_sound(sample_rate=8000, master_gain=0.5)
    psg.set_tone(0, frequency_hz=220.0, volume=0)
    psg.set_tone_waveform(0, Waveform.SINE)
    assert _rms(psg.render(2000)) > 0.02


def test_midi_note_helpers() -> None:
    psg = tandy_sound(sample_rate=8000, master_gain=0.5)
    sn76496_note_on(psg, 0, 69, velocity=100)
    assert _rms(psg.render(1000)) > 0.02
    sn76496_note_off(psg, 0)
    assert _rms(psg.render(500)) < 1e-6


def test_three_channels_mix() -> None:
    psg = tandy_sound(sample_rate=8000, master_gain=0.3)
    psg.note_on(0, 262.0, volume=2)
    psg.note_on(1, 330.0, volume=2)
    psg.note_on(2, 392.0, volume=2)
    assert _rms(psg.render(2000)) > 0.05


def test_soundchip_protocol() -> None:
    psg: SN76496 = sega_psg()
    assert psg.channels_out == 1
    psg.reset()
