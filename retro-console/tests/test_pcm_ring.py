"""PcmRing unit tests (no AudioQueue required)."""

from __future__ import annotations

import struct

import pytest

from rwt_rconsole import PcmRing


def _mono_bytes(samples: list[float]) -> bytes:
    return struct.pack(f"{len(samples)}f", *samples)


def _stereo_bytes(frames: list[tuple[float, float]]) -> bytes:
    flat: list[float] = []
    for l, r in frames:
        flat.append(l)
        flat.append(r)
    return struct.pack(f"{len(flat)}f", *flat)


def test_push_mono_upmix_and_pull() -> None:
    ring = PcmRing(sample_rate=8000, channels=2, capacity_frames=1000)
    n = ring.push_mono(_mono_bytes([0.5, -0.5, 0.25]))
    assert n == 3
    assert ring.available == 3

    out = bytearray(3 * 2 * 4)
    ring.pull(out)
    samples = struct.unpack("6f", out)
    assert samples[0] == pytest.approx(0.5)
    assert samples[1] == pytest.approx(0.5)
    assert samples[2] == pytest.approx(-0.5)
    assert samples[3] == pytest.approx(-0.5)
    assert ring.available == 0


def test_underrun_silence_and_counter() -> None:
    ring = PcmRing(sample_rate=8000, channels=1, capacity_frames=64)
    out = bytearray(10 * 4)
    ring.pull(out)
    assert struct.unpack("10f", out) == tuple(0.0 for _ in range(10))
    assert ring.underruns >= 10


def test_latency_ms_from_capacity() -> None:
    ring = PcmRing(sample_rate=1000, channels=1, latency_ms=50)
    # 50 ms @ 1000 Hz = 50 frames (min floor 256 in C for small rates...)
    # C uses max(256, computed) when capacity from latency — at 1000 Hz 50ms = 50 → floor 256
    assert ring.capacity >= 50
    assert ring.latency_ms == pytest.approx(
        1000.0 * ring.capacity / ring.sample_rate, rel=1e-6
    )


def test_explicit_capacity() -> None:
    ring = PcmRing(sample_rate=44100, channels=2, capacity_frames=512)
    assert ring.capacity == 512


def test_push_full_returns_partial() -> None:
    ring = PcmRing(sample_rate=8000, channels=1, capacity_frames=8)
    n = ring.push_mono(_mono_bytes([1.0] * 12))
    assert n == 8
    assert ring.available == 8
