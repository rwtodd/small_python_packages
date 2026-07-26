"""IBM PC Speaker (8253/8254 PIT square wave, optional other waveforms)."""

from __future__ import annotations

from . import _chips
from .chip import Waveform

PIT_CLOCK_HZ = float(_chips.PIT_CLOCK_HZ)


class PCSpeaker:
    """Single-channel PC speaker emulator.

    Historically outputs a square wave gated by the 8255 speaker bit and
    timed by PIT channel 2. Non-square :class:`Waveform` values are supported
    for creative use but are not hardware-accurate.

    Realtime host playback: render mono float32 and push into an
    ``rwt_rconsole.PcmRing`` (this package does not own the audio device).
    """

    __slots__ = ("_core",)

    def __init__(
        self,
        sample_rate: float = 44100.0,
        *,
        amplitude: float = 0.25,
        waveform: Waveform | int = Waveform.SQUARE,
    ) -> None:
        self._core = _chips.PCSpeakerCore(sample_rate, amplitude)
        self.set_waveform(waveform)

    @property
    def name(self) -> str:
        return "pc_speaker"

    @property
    def sample_rate(self) -> float:
        return float(self._core.sample_rate)

    @property
    def channels_out(self) -> int:
        return 1

    @property
    def frequency_hz(self) -> float:
        return float(self._core.frequency_hz)

    @property
    def gate(self) -> bool:
        return bool(self._core.gate)

    @property
    def waveform(self) -> Waveform:
        return Waveform(int(self._core.waveform))

    @property
    def amplitude(self) -> float:
        return float(self._core.amplitude)

    def reset(self) -> None:
        self._core.reset()

    def set_frequency_hz(self, frequency: float | None) -> None:
        """Set tone frequency in Hz. ``None`` or ``0`` silences the oscillator."""
        self._core.set_frequency_hz(0.0 if frequency is None else float(frequency))

    def set_pit_divisor(self, divisor: int) -> None:
        """Program PIT channel 2 divisor (``freq = 1_193_182 / divisor``)."""
        self._core.set_pit_divisor(int(divisor))

    def set_gate(self, on: bool) -> None:
        """Enable or disable the speaker output (port 0x61 style gate)."""
        self._core.set_gate(bool(on))

    def beep(self, frequency_hz: float, *, gate: bool = True) -> None:
        """Convenience: set frequency and open the gate."""
        self.set_frequency_hz(frequency_hz)
        self.set_gate(gate)

    def silence(self) -> None:
        """Close the gate (note-off equivalent)."""
        self.set_gate(False)

    def set_waveform(self, waveform: Waveform | int) -> None:
        self._core.set_waveform(int(waveform))

    def set_amplitude(self, amplitude: float) -> None:
        self._core.set_amplitude(float(amplitude))

    def write(self, address: int, value: int) -> None:
        """Minimal bus-style programming.

        * ``address == 0``: full 16-bit PIT divisor.
        * ``address == 1``: gate (0/1).
        """
        if address == 0:
            self.set_pit_divisor(value & 0xFFFF)
        elif address == 1:
            self.set_gate(bool(value & 1))
        else:
            raise ValueError(f"PCSpeaker write: unknown address {address}")

    def read(self, address: int) -> int:
        if address == 1:
            return 1 if self.gate else 0
        raise ValueError(f"PCSpeaker read: unknown address {address}")

    def render_into(self, destination: memoryview | object) -> None:
        """Fill *destination* with mono float32 samples (advances the oscillator)."""
        self._core.render_into(destination)

    def render(self, frames: int) -> memoryview:
        """Allocate and fill *frames* mono float32 samples."""
        buf = memoryview(bytearray(frames * 4)).cast("f")
        self.render_into(buf)
        return buf
