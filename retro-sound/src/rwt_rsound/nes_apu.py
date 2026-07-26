"""NES APU (2A03 / 2A07) — cycle-stepped for emulator CPU/PPU interleaving."""

from __future__ import annotations

from enum import IntEnum
from typing import Callable

from . import _chips

NTSC_CPU_HZ = float(_chips.NES_NTSC_CPU_HZ)
PAL_CPU_HZ = float(_chips.NES_PAL_CPU_HZ)


class NesRegion(IntEnum):
    """Video system / CPU clock profile."""

    NTSC = _chips.NES_REGION_NTSC
    PAL = _chips.NES_REGION_PAL


class NesApu:
    """Ricoh 2A03/2A07 audio processing unit.

    **Emulator integration:**

    1. Match region/CPU clock to the rest of the machine.
    2. Each timeslice: :meth:`clock` (*cpu_cycles*) — samples accumulate.
    3. :meth:`drain_into` / :meth:`samples_available` → push mono float32 into
       an ``rwt_rconsole.PcmRing`` for host playback.
    4. Bus: :meth:`write` / :meth:`read` for ``$4000–$4017``.
    5. Optional :meth:`set_dmc_reader`; poll :meth:`irq_pending`.

    **Offline:** :meth:`render_into` / :meth:`render` (no manual ``clock``).
    """

    __slots__ = ("_core", "_region")

    def __init__(
        self,
        sample_rate: float = 44100.0,
        *,
        region: NesRegion | int = NesRegion.NTSC,
        cpu_clock_hz: float | None = None,
        master_gain: float = 0.5,
    ) -> None:
        r = int(region)
        cpu = 0.0 if cpu_clock_hz is None else float(cpu_clock_hz)
        self._region = NesRegion(r)
        self._core = _chips.NesApuCore(
            float(sample_rate),
            r,
            cpu,
            float(master_gain),
        )

    @property
    def name(self) -> str:
        return f"nes_apu_{self._region.name.lower()}"

    @property
    def region(self) -> NesRegion:
        return self._region

    @property
    def sample_rate(self) -> float:
        return float(self._core.sample_rate)

    @property
    def cpu_clock_hz(self) -> float:
        return float(self._core.cpu_clock_hz)

    @property
    def channels_out(self) -> int:
        return 1

    def reset(self) -> None:
        self._core.reset()

    def clock(self, cpu_cycles: int) -> int:
        """Advance the APU by *cpu_cycles* (same unit as the 6502).

        Returns the number of PCM samples now queued in the ring buffer.
        Call this from the emulator main loop in lockstep with the CPU
        (and typically the PPU catch-up for the same interval).
        """
        return int(self._core.clock(int(cpu_cycles)))

    def write(self, address: int, value: int) -> None:
        """CPU write to APU registers (``$4000–$4017``)."""
        self._core.write(int(address), int(value) & 0xFF)

    def read(self, address: int) -> int:
        """CPU read (meaningful for ``$4015`` status; clears frame IRQ)."""
        return int(self._core.read(int(address)))

    def samples_available(self) -> int:
        return int(self._core.samples_available())

    def irq_pending(self) -> bool:
        """Frame IRQ and/or DMC IRQ flag set (wire to CPU /IRQ)."""
        return bool(self._core.irq_pending())

    def set_dmc_reader(self, reader: Callable[[int], int] | None) -> None:
        """Provide ``reader(cpu_address) -> byte`` for DMC DMA fetches.

        Emulators should map this through the same CPU memory view used for
        instruction fetches (PRG ROM, RAM, etc.). ``None`` yields silence
        bytes (0x00) when the DMC needs data.
        """
        self._core.set_dmc_reader(reader)

    def drain_into(self, destination: memoryview | object) -> None:
        """Copy queued float32 mono samples; pad with zeros on underrun."""
        self._core.drain_into(destination)

    def render_into(self, destination: memoryview | object) -> None:
        """Offline: clock the APU until *destination* is filled with float32."""
        self._core.render_into(destination)

    def render(self, frames: int) -> memoryview:
        buf = memoryview(bytearray(frames * 4)).cast("f")
        self.render_into(buf)
        return buf

    # --- high-level channel helpers (not a substitute for register writes) ---

    def enable_channels(
        self,
        *,
        pulse1: bool = False,
        pulse2: bool = False,
        triangle: bool = False,
        noise: bool = False,
        dmc: bool = False,
    ) -> None:
        """Write ``$4015`` channel enables."""
        v = 0
        if pulse1:
            v |= 0x01
        if pulse2:
            v |= 0x02
        if triangle:
            v |= 0x04
        if noise:
            v |= 0x08
        if dmc:
            v |= 0x10
        self.write(0x4015, v)

    def set_pulse(
        self,
        channel: int,
        *,
        duty: int = 2,
        volume: int = 15,
        constant_volume: bool = True,
        halt_length: bool = True,
        timer: int | None = None,
        frequency_hz: float | None = None,
        length_index: int = 1,
    ) -> None:
        """Configure pulse channel 0 or 1 with common defaults for tones.

        *timer* is the 11-bit period register; or pass *frequency_hz* and it is
        converted with ``timer = cpu_clock / (16 * f) - 1``.
        """
        if channel not in (0, 1):
            raise ValueError("pulse channel must be 0 or 1")
        base = 0x4000 if channel == 0 else 0x4004
        reg0 = ((duty & 3) << 6)
        if halt_length:
            reg0 |= 0x20
        if constant_volume:
            reg0 |= 0x10
        reg0 |= volume & 0x0F
        self.write(base, reg0)
        self.write(base + 1, 0x08)  # sweep off (negate bit unused)

        if frequency_hz is not None:
            if frequency_hz <= 0:
                timer = 0
            else:
                timer = int(round(self.cpu_clock_hz / (16.0 * float(frequency_hz)) - 1.0))
                timer = max(0, min(0x7FF, timer))
        if timer is None:
            timer = 0x0FE  # ~middle C-ish at NTSC
        self.write(base + 2, timer & 0xFF)
        self.write(base + 3, ((length_index & 0x1F) << 3) | ((timer >> 8) & 7))

    def set_triangle(
        self,
        *,
        timer: int | None = None,
        frequency_hz: float | None = None,
        length_index: int = 1,
        linear: int = 0x7F,
        control: bool = True,
    ) -> None:
        """Configure triangle. Frequency uses ``cpu / (32 * (t+1))``."""
        reg8 = (0x80 if control else 0) | (linear & 0x7F)
        self.write(0x4008, reg8)
        if frequency_hz is not None:
            if frequency_hz <= 0:
                timer = 0
            else:
                timer = int(round(self.cpu_clock_hz / (32.0 * float(frequency_hz)) - 1.0))
                timer = max(0, min(0x7FF, timer))
        if timer is None:
            timer = 0x1FB
        self.write(0x400A, timer & 0xFF)
        self.write(0x400B, ((length_index & 0x1F) << 3) | ((timer >> 8) & 7))

    def set_noise(
        self,
        *,
        period_index: int = 4,
        volume: int = 8,
        constant_volume: bool = True,
        tone_mode: bool = False,
        length_index: int = 1,
        halt_length: bool = True,
    ) -> None:
        reg = 0
        if halt_length:
            reg |= 0x20
        if constant_volume:
            reg |= 0x10
        reg |= volume & 0x0F
        self.write(0x400C, reg)
        self.write(0x400E, (0x80 if tone_mode else 0) | (period_index & 0x0F))
        self.write(0x400F, (length_index & 0x1F) << 3)

    def note_on_pulse(
        self,
        channel: int,
        frequency_hz: float,
        *,
        volume: int = 10,
        duty: int = 2,
        enable_mask: int | None = None,
    ) -> None:
        """Enable a pulse channel and start a sustained tone.

        *enable_mask* is the ``$4015`` value written (default: only this
        pulse channel). Pass a wider mask to keep other channels enabled.
        """
        if channel not in (0, 1):
            raise ValueError("pulse channel must be 0 or 1")
        if enable_mask is None:
            enable_mask = 1 << channel
        else:
            enable_mask = int(enable_mask) | (1 << channel)
        self.write(0x4015, enable_mask & 0x1F)
        self.set_pulse(
            channel,
            duty=duty,
            volume=volume,
            constant_volume=True,
            halt_length=True,
            frequency_hz=frequency_hz,
            length_index=1,
        )


def nes_apu_ntsc(
    sample_rate: float = 44100.0,
    *,
    cpu_clock_hz: float | None = None,
    master_gain: float = 0.5,
) -> NesApu:
    return NesApu(
        sample_rate,
        region=NesRegion.NTSC,
        cpu_clock_hz=cpu_clock_hz,
        master_gain=master_gain,
    )


def nes_apu_pal(
    sample_rate: float = 44100.0,
    *,
    cpu_clock_hz: float | None = None,
    master_gain: float = 0.5,
) -> NesApu:
    return NesApu(
        sample_rate,
        region=NesRegion.PAL,
        cpu_clock_hz=cpu_clock_hz,
        master_gain=master_gain,
    )
