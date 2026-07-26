"""Host-side PCM ring for realtime audio (see ``rwt_rconsole._pcm``)."""

from __future__ import annotations

from typing import Any

from . import _pcm
from .audio import AudioChannels, AudioConfig

DEFAULT_LATENCY_MS = float(_pcm.DEFAULT_LATENCY_MS)
DEFAULT_FRAMES_PER_BUFFER = int(_pcm.DEFAULT_FRAMES_PER_BUFFER)
DEFAULT_BUFFER_COUNT = int(_pcm.DEFAULT_BUFFER_COUNT)
HAS_RING_PLAYER = bool(_pcm.HAS_RING_PLAYER)


class PcmRing:
    """Float32 PCM ring in **device channel layout** (interleaved).

    Producers (emu loop, music thread) call :meth:`push` / :meth:`push_mono`.
    The AudioQueue path drains via pure C (see :func:`create_audio_from_ring`).

    Capacity defaults to about *latency_ms* of audio at *sample_rate*
    (default **25 ms**). That is application-side buffering only; the device
    adds its own queue depth (see *frames_per_buffer* × *buffer_count* on the
    player — also tunable, not fixed by Apple at 3×512).
    """

    __slots__ = ("_core",)

    def __init__(
        self,
        *,
        sample_rate: int = 44100,
        channels: int | AudioChannels = 2,
        latency_ms: float = DEFAULT_LATENCY_MS,
        capacity_frames: int | None = None,
        config: AudioConfig | None = None,
    ) -> None:
        if config is not None:
            sample_rate = int(config.sample_rate)
            channels = int(config.channels)
        ch = int(channels)
        cap = 0 if capacity_frames is None else int(capacity_frames)
        self._core = _pcm.PcmRing(
            sample_rate,
            ch,
            float(latency_ms),
            cap,
        )

    @property
    def sample_rate(self) -> int:
        return int(self._core.sample_rate)

    @property
    def channels(self) -> int:
        return int(self._core.channels)

    @property
    def capacity(self) -> int:
        """Capacity in frames."""
        return int(self._core.capacity)

    @property
    def available(self) -> int:
        """Frames currently queued."""
        return int(self._core.available)

    @property
    def underruns(self) -> int:
        return int(self._core.underruns)

    @property
    def latency_ms(self) -> float:
        """Ring capacity as milliseconds at this sample rate."""
        return float(self._core.latency_ms)

    def push(self, interleaved: Any) -> int:
        """Push device-layout float32 samples. Returns frames written."""
        return int(self._core.push(_as_float_bytes(interleaved)))

    def push_mono(self, mono: Any) -> int:
        """Push mono float32 samples (upmixed to ring channels). Returns frames written."""
        return int(self._core.push_mono(_as_float_bytes(mono)))

    def pull(self, destination: Any) -> None:
        """Pull into a writable float32 buffer (tests / manual drain)."""
        self._core.pull(destination)

    def clear(self) -> None:
        self._core.clear()

    @property
    def _raw(self) -> Any:
        return self._core


def _as_float_bytes(buf: Any) -> Any:
    """Normalize to a bytes-like float32 buffer for the C extension."""
    mv = memoryview(buf)
    if mv.format == "f":
        return mv.cast("B") if mv.ndim == 1 else mv
    if mv.format in ("B", "b", "c"):
        return mv
    # memoryview of array.array('f') etc.
    try:
        return mv.cast("B")
    except TypeError:
        return mv


def create_audio_from_ring(
    config: AudioConfig,
    ring: PcmRing,
    *,
    frames_per_buffer: int = DEFAULT_FRAMES_PER_BUFFER,
    buffer_count: int = DEFAULT_BUFFER_COUNT,
) -> Any:
    """Play *ring* through the host device with a **pure-C** AudioQueue callback.

    No Python runs on the audio thread. Requires macOS (AudioToolbox).

    Parameters
    ----------
    frames_per_buffer:
        Size of each AudioQueue buffer in frames (default **256**).
        Fully tunable — not an OS requirement.
    buffer_count:
        Number of AQ buffers kept in flight (default **3**).
        Fully tunable — the old 3×512 default was an application choice only.

    Approximate **device** latency ≈
    ``buffer_count * frames_per_buffer / sample_rate`` seconds,
    **plus** the ring's own ``latency_ms`` capacity (how far ahead you pre-fill).
    """
    if not HAS_RING_PLAYER:
        raise RuntimeError(
            "create_audio_from_ring requires macOS AudioQueue support "
            "(rwt_rconsole._pcm.RingPlayer)."
        )
    if int(config.channels) != ring.channels:
        raise ValueError(
            f"config.channels ({int(config.channels)}) != ring.channels ({ring.channels})"
        )
    if int(config.sample_rate) != ring.sample_rate:
        # Allow mild mismatch but warn via error for safety
        raise ValueError(
            f"config.sample_rate ({config.sample_rate}) != ring.sample_rate ({ring.sample_rate})"
        )
    if config.format is not None:
        from .audio import AudioSampleFormat

        if config.format is not AudioSampleFormat.FLOAT32:
            raise ValueError("create_audio_from_ring currently supports FLOAT32 only")

    return _pcm.RingPlayer(
        ring._raw,
        int(config.sample_rate),
        int(config.channels),
        int(frames_per_buffer),
        int(buffer_count),
    )
