"""TI SN76489-family PSG: Tandy 1000 / PCjr (SN76496) and Sega (SMS/GG/MD)."""

from __future__ import annotations

from enum import IntEnum

from . import _chips
from .chip import Waveform

# NTSC colorburst-derived clock used by Tandy/PCjr and SMS PSG in many systems.
DEFAULT_CLOCK_HZ = 3_579_545.0


class SN76496Variant(IntEnum):
    """Hardware profiles for the shared SN76489-family core.

    Differences (noise LFSR width/taps) stay inside the C core.
    """

    TANDY = _chips.VARIANT_TANDY  # SN76496 / NCR8496 (PCjr, Tandy 1000)
    SEGA = _chips.VARIANT_SEGA  # Master System / Game Gear / Genesis PSG


class SN76496:
    """Three tone channels + noise, TI latch/data register protocol.

    Use :class:`SN76496Variant.TANDY` or :class:`SN76496Variant.SEGA` (or the
    factory helpers :func:`tandy_sound` / :func:`sega_psg`). Tone channels
    default to square waves; optional non-square :class:`Waveform` values are
    creative extensions only.

    Realtime host playback: :meth:`render` mono float32 and push into
    ``rwt_rconsole.PcmRing``.
    """

    __slots__ = ("_core", "_variant")

    def __init__(
        self,
        variant: SN76496Variant | int = SN76496Variant.TANDY,
        *,
        sample_rate: float = 44100.0,
        clock_hz: float = DEFAULT_CLOCK_HZ,
        master_gain: float = 0.25,
    ) -> None:
        v = int(variant)
        self._variant = SN76496Variant(v)
        self._core = _chips.SN76496Core(
            v, float(sample_rate), float(clock_hz), float(master_gain)
        )

    @property
    def name(self) -> str:
        return f"sn76496_{self._variant.name.lower()}"

    @property
    def variant(self) -> SN76496Variant:
        return self._variant

    @property
    def sample_rate(self) -> float:
        return float(self._core.sample_rate)

    @property
    def clock_hz(self) -> float:
        return float(self._core.clock_hz)

    @property
    def channels_out(self) -> int:
        return 1

    def reset(self) -> None:
        self._core.reset()

    def write(self, value: int, address: int = 0) -> None:
        """Write one data byte to the PSG (single I/O port on Tandy/SMS).

        *address* is accepted for API uniformity and ignored.
        """
        self._core.write(int(address), int(value) & 0xFF)

    def read(self, address: int = 0) -> int:
        """PSG is write-only; always returns 0xFF."""
        return 0xFF

    def set_tone(
        self,
        channel: int,
        *,
        period: int | None = None,
        volume: int | None = None,
        frequency_hz: float | None = None,
    ) -> None:
        """Configure a tone channel (0..2).

        Prefer *period* (10-bit) or *frequency_hz*. *volume* is attenuation
        0 (loud) .. 15 (mute).
        """
        if channel < 0 or channel > 2:
            raise ValueError("channel must be 0..2")
        p = period
        if frequency_hz is not None:
            if frequency_hz <= 0:
                p = 0
            else:
                p = int(round(self.clock_hz / (32.0 * float(frequency_hz))))
                p = max(1, min(0x3FF, p))
        kwargs: dict[str, int] = {"channel": int(channel)}
        if p is not None:
            kwargs["period"] = int(p) & 0x3FF
        if volume is not None:
            kwargs["volume"] = int(volume) & 0x0F
        if len(kwargs) == 1:
            return
        self._core.set_tone(**kwargs)

    def set_noise(
        self,
        *,
        control: int | None = None,
        volume: int | None = None,
        white: bool | None = None,
        rate: int | None = None,
    ) -> None:
        """Configure the noise channel.

        *control* is the raw 4-bit noise register, or set *white* / *rate* (0..3).
        """
        ctrl = control
        if white is not None or rate is not None:
            c = 0 if ctrl is None else int(ctrl) & 0x0F
            if rate is not None:
                if rate < 0 or rate > 3:
                    raise ValueError("rate must be 0..3")
                c = (c & ~0x03) | (int(rate) & 0x03)
            if white is not None:
                c = (c & ~0x04) | (0x04 if white else 0)
            ctrl = c
        kwargs: dict[str, int] = {}
        if ctrl is not None:
            kwargs["control"] = int(ctrl) & 0x0F
        if volume is not None:
            kwargs["volume"] = int(volume) & 0x0F
        if kwargs:
            self._core.set_noise(**kwargs)

    def set_tone_waveform(self, channel: int, waveform: Waveform | int) -> None:
        """Non-historical waveform for tone channel 0..2 (default square)."""
        self._core.set_tone_waveform(int(channel), int(waveform))

    def tone_frequency(self, channel: int) -> float:
        return float(self._core.tone_frequency(int(channel)))

    def note_on(
        self,
        channel: int,
        frequency_hz: float,
        *,
        volume: int = 0,
    ) -> None:
        """Start a tone at *frequency_hz* with attenuation *volume* (0=loud)."""
        self.set_tone(channel, frequency_hz=frequency_hz, volume=volume)

    def note_off(self, channel: int) -> None:
        """Mute a tone channel (attenuation 15)."""
        self.set_tone(channel, volume=15)

    def render_into(self, destination: memoryview | object) -> None:
        """Fill *destination* with mono float32 samples."""
        self._core.render_into(destination)

    def render(self, frames: int) -> memoryview:
        buf = memoryview(bytearray(frames * 4)).cast("f")
        self.render_into(buf)
        return buf

    def write_tone_period(self, channel: int, period: int) -> None:
        """Emit the two-byte TI register sequence for a tone period."""
        if channel < 0 or channel > 2:
            raise ValueError("channel must be 0..2")
        period &= 0x3FF
        reg = channel * 2
        self.write(0x80 | (reg << 4) | (period & 0x0F))
        self.write((period >> 4) & 0x3F)

    def write_volume(self, channel: int, volume: int) -> None:
        """channel 0..2 tone, channel 3 noise; volume attenuation 0..15."""
        if channel < 0 or channel > 3:
            raise ValueError("channel must be 0..3")
        reg = channel * 2 + 1
        self.write(0x80 | (reg << 4) | (volume & 0x0F))

    def write_noise_control(self, control: int) -> None:
        self.write(0x80 | (6 << 4) | (control & 0x0F))


def tandy_sound(
    *,
    sample_rate: float = 44100.0,
    clock_hz: float = DEFAULT_CLOCK_HZ,
    master_gain: float = 0.25,
) -> SN76496:
    """PCjr / Tandy 1000 three-voice + noise (SN76496 / NCR8496 profile)."""
    return SN76496(
        SN76496Variant.TANDY,
        sample_rate=sample_rate,
        clock_hz=clock_hz,
        master_gain=master_gain,
    )


def sega_psg(
    *,
    sample_rate: float = 44100.0,
    clock_hz: float = DEFAULT_CLOCK_HZ,
    master_gain: float = 0.25,
) -> SN76496:
    """Sega Master System / Game Gear / Genesis PSG profile."""
    return SN76496(
        SN76496Variant.SEGA,
        sample_rate=sample_rate,
        clock_hz=clock_hz,
        master_gain=master_gain,
    )
