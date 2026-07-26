"""Shared types and the SoundChip protocol."""

from __future__ import annotations

from enum import IntEnum
from typing import Protocol, runtime_checkable


class Waveform(IntEnum):
    """Oscillator shape for tone channels.

    ``SQUARE`` is the historically accurate output for PC Speaker and
    SN76489-family tone generators. Other values are creative extensions.
    """

    SQUARE = 0
    TRIANGLE = 1
    SAWTOOTH = 2
    SINE = 3


@runtime_checkable
class SoundChip(Protocol):
    """Minimal interface every chip façade should provide."""

    @property
    def name(self) -> str: ...

    @property
    def sample_rate(self) -> float: ...

    @property
    def channels_out(self) -> int: ...

    def reset(self) -> None: ...

    def render_into(self, destination: memoryview | object) -> None:
        """Fill *destination* with interleaved float32 PCM frames."""
        ...
