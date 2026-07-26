"""NES APU tests — registers, cycle stepping, audio energy."""

from __future__ import annotations

import math

import pytest

from rwt_rsound import (
    NTSC_CPU_HZ,
    NesApu,
    NesRegion,
    nes_apu_ntsc,
    nes_pulse_note_on,
)


def _rms(samples: memoryview) -> float:
    n = len(samples)
    if n == 0:
        return 0.0
    acc = sum(float(s) * float(s) for s in samples)
    return math.sqrt(acc / n)


def test_region_clocks() -> None:
    apu = nes_apu_ntsc(sample_rate=48000)
    assert apu.region is NesRegion.NTSC
    assert apu.cpu_clock_hz == pytest.approx(NTSC_CPU_HZ)
    assert apu.channels_out == 1


def test_silent_when_disabled() -> None:
    apu = NesApu(sample_rate=8000)
    # program a tone but never enable $4015
    apu.set_pulse(0, frequency_hz=440.0, volume=15)
    buf = apu.render(2000)
    assert _rms(buf) < 0.02


def test_pulse_has_energy() -> None:
    apu = NesApu(sample_rate=8000, master_gain=0.8)
    apu.note_on_pulse(0, 440.0, volume=12)
    buf = apu.render(4000)
    assert _rms(buf) > 0.02


def test_triangle_has_energy() -> None:
    apu = NesApu(sample_rate=8000, master_gain=0.8)
    apu.enable_channels(triangle=True)
    apu.set_triangle(frequency_hz=220.0, linear=0x7F, control=True)
    buf = apu.render(4000)
    assert _rms(buf) > 0.01


def test_noise_has_energy() -> None:
    apu = NesApu(sample_rate=8000, master_gain=0.8)
    apu.enable_channels(noise=True)
    apu.set_noise(period_index=2, volume=10)
    buf = apu.render(6000)
    assert _rms(buf) > 0.01


def test_register_status_length() -> None:
    apu = NesApu(sample_rate=8000)
    apu.write(0x4015, 0x01)
    # length load + timer
    apu.write(0x4000, 0x3F)  # halt + const + vol
    apu.write(0x4002, 0x00)
    apu.write(0x4003, 0x08)  # length index 1 → 254
    status = apu.read(0x4015)
    assert status & 0x01


def test_emulator_style_clock_and_drain() -> None:
    """Simulate CPU timeslices: clock N cycles, then drain PCM."""
    apu = NesApu(sample_rate=44100, master_gain=0.7)
    apu.note_on_pulse(0, 523.25, volume=10)

    total = 0
    pcm = bytearray()
    # ~0.1 s of CPU time in chunks of ~1000 cycles
    cycles_target = int(0.1 * apu.cpu_clock_hz)
    stepped = 0
    while stepped < cycles_target:
        chunk = 1000
        avail = apu.clock(chunk)
        stepped += chunk
        if avail > 0:
            buf = memoryview(bytearray(avail * 4)).cast("f")
            apu.drain_into(buf)
            pcm.extend(buf.cast("B"))
            total += avail

    assert total > 1000  # got a meaningful number of samples
    samples = memoryview(pcm).cast("f")
    assert _rms(samples) > 0.01


def test_dmc_reader_called() -> None:
    apu = NesApu(sample_rate=8000)
    fetches: list[int] = []

    def reader(addr: int) -> int:
        fetches.append(addr)
        return 0xAA

    apu.set_dmc_reader(reader)
    apu.write(0x4010, 0x00)  # rate 0, no irq
    apu.write(0x4012, 0x00)  # addr $C000
    apu.write(0x4013, 0x01)  # length = 17 bytes
    apu.write(0x4015, 0x10)  # enable DMC
    # clock enough for several bit clocks
    apu.clock(50_000)
    assert len(fetches) > 0
    assert fetches[0] == 0xC000


def test_midi_pulse_helper() -> None:
    apu = NesApu(sample_rate=8000, master_gain=0.8)
    nes_pulse_note_on(apu, 0, 69, velocity=100)
    assert _rms(apu.render(3000)) > 0.02


def test_two_pulses() -> None:
    apu = NesApu(sample_rate=8000, master_gain=0.6)
    apu.note_on_pulse(0, 262.0, volume=8, enable_mask=0x03)
    apu.note_on_pulse(1, 330.0, volume=8, enable_mask=0x03)
    assert _rms(apu.render(4000)) > 0.02


def test_irq_flag_mode0() -> None:
    apu = NesApu(sample_rate=8000)
    # 4-step mode, IRQ enabled (bit 6 clear)
    apu.write(0x4017, 0x00)
    # Run past one full 4-step frame (~29829 CPU cycles)
    apu.clock(30_000)
    assert apu.irq_pending()
    # read $4015 clears frame IRQ
    apu.read(0x4015)
    assert not apu.irq_pending()
