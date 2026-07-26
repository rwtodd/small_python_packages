"""Streaming audio types, null device, and backend registration."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from typing import Protocol, runtime_checkable


class AudioChannels(IntEnum):
    MONO = 1
    STEREO = 2


class AudioSampleFormat(IntEnum):
    FLOAT32 = 1
    INT16 = 2
    INT8 = 3
    UINT8 = 4


class AudioPlaybackState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


@dataclass(frozen=True, slots=True)
class AudioConfig:
    sample_rate: int = 44100
    channels: AudioChannels = AudioChannels.STEREO
    format: AudioSampleFormat = AudioSampleFormat.FLOAT32
    reverb: int = 0  # 0..255

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive.")
        if self.channels not in (AudioChannels.MONO, AudioChannels.STEREO):
            raise ValueError("channels must be MONO or STEREO.")
        if self.format not in (
            AudioSampleFormat.FLOAT32,
            AudioSampleFormat.INT16,
            AudioSampleFormat.INT8,
            AudioSampleFormat.UINT8,
        ):
            raise ValueError(f"Unsupported sample format: {self.format}.")
        if not 0 <= self.reverb <= 255:
            raise ValueError("reverb must be 0..255.")


def sample_size(fmt: AudioSampleFormat) -> int:
    """Bytes per sample for *fmt*."""
    if fmt is AudioSampleFormat.FLOAT32:
        return 4
    if fmt is AudioSampleFormat.INT16:
        return 2
    if fmt in (AudioSampleFormat.INT8, AudioSampleFormat.UINT8):
        return 1
    raise ValueError(f"Unsupported sample format: {fmt}")


def frame_size(config: AudioConfig) -> int:
    """Bytes per multi-channel frame."""
    return sample_size(config.format) * int(config.channels)


# Back-compat aliases
sample_size_in_bytes = sample_size
frame_size_in_bytes = frame_size


def validate_audio_config(config: AudioConfig) -> None:
    """No-op when *config* was built normally (validated in ``__post_init__``)."""
    # Re-run checks for configs that bypassed __post_init__ (unlikely).
    AudioConfig(
        sample_rate=config.sample_rate,
        channels=config.channels,
        format=config.format,
        reverb=config.reverb,
    )


AudioCallback = Callable[[memoryview], None]


@runtime_checkable
class RetroAudio(Protocol):
    @property
    def config(self) -> AudioConfig: ...

    @property
    def state(self) -> AudioPlaybackState: ...

    def play(self) -> None: ...
    def pause(self) -> None: ...
    def stop(self) -> None: ...

    @property
    def has_reverb_support(self) -> bool: ...

    @property
    def reverb(self) -> int: ...

    @reverb.setter
    def reverb(self, value: int) -> None: ...

    @property
    def last_error(self) -> BaseException | None: ...

    def close(self) -> None: ...

    def __enter__(self) -> RetroAudio: ...
    def __exit__(self, *exc: object) -> None: ...


class AudioBackend(Protocol):
    def suggested_config(self) -> AudioConfig: ...
    def create(self, config: AudioConfig, callback: AudioCallback) -> RetroAudio: ...


_audio_backend: AudioBackend | None = None
_audio_lock = threading.Lock()


def register_audio_backend(backend: AudioBackend) -> None:
    with _audio_lock:
        global _audio_backend
        _audio_backend = backend


def clear_audio_backend() -> None:
    with _audio_lock:
        global _audio_backend
        _audio_backend = None


def get_audio_backend() -> AudioBackend | None:
    with _audio_lock:
        return _audio_backend


def _as_bytes(destination: memoryview) -> memoryview:
    """Normalize to a plain uint8 memoryview (ctypes often yields endian-prefixed formats)."""
    if destination.format == "B":
        return destination
    return destination.cast("B")


def as_float32(destination: memoryview) -> memoryview:
    """View raw bytes as float32 samples (native endian)."""
    return _as_bytes(destination).cast("f")


def as_int16(destination: memoryview) -> memoryview:
    return _as_bytes(destination).cast("h")


def as_int8(destination: memoryview) -> memoryview:
    return _as_bytes(destination).cast("b")


class NullAudio:
    """In-memory / test audio device."""

    def __init__(self, config: AudioConfig, callback: AudioCallback) -> None:
        self._config = config
        self._callback = callback
        self._lock = threading.Lock()
        self._state = AudioPlaybackState.STOPPED
        self._reverb = config.reverb
        self._last_error: BaseException | None = None
        self._closed = False

    @property
    def config(self) -> AudioConfig:
        return self._config

    @property
    def state(self) -> AudioPlaybackState:
        with self._lock:
            return self._state

    def play(self) -> None:
        with self._lock:
            if not self._closed:
                self._state = AudioPlaybackState.PLAYING

    def pause(self) -> None:
        with self._lock:
            if not self._closed and self._state is AudioPlaybackState.PLAYING:
                self._state = AudioPlaybackState.PAUSED

    def stop(self) -> None:
        with self._lock:
            if not self._closed:
                self._state = AudioPlaybackState.STOPPED

    @property
    def has_reverb_support(self) -> bool:
        return True

    @property
    def reverb(self) -> int:
        with self._lock:
            return self._reverb

    @reverb.setter
    def reverb(self, value: int) -> None:
        if not 0 <= value <= 255:
            raise ValueError("reverb must be 0..255.")
        with self._lock:
            self._reverb = value

    @property
    def last_error(self) -> BaseException | None:
        with self._lock:
            return self._last_error

    def simulate_render(self, destination: memoryview | bytearray) -> None:
        """Simulate a callback render tick for testing."""
        mv = memoryview(destination).cast("B")
        with self._lock:
            playing = self._state is AudioPlaybackState.PLAYING
        if playing:
            try:
                self._callback(mv)
            except BaseException as ex:
                with self._lock:
                    self._last_error = ex
                    self._state = AudioPlaybackState.STOPPED
                mv[:] = b"\x00" * len(mv)
        else:
            mv[:] = b"\x00" * len(mv)

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._closed = True
                self._state = AudioPlaybackState.STOPPED

    def __enter__(self) -> NullAudio:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# Back-compat alias
NullRetroAudio = NullAudio


def suggested_audio_config() -> AudioConfig:
    """Suggested config from the registered backend, or a standard default."""
    backend = get_audio_backend()
    if backend is not None:
        return backend.suggested_config()
    return AudioConfig()


# Back-compat alias
get_suggested_audio_config = suggested_audio_config


def create_audio(
    config: AudioConfig,
    callback: AudioCallback,
    *,
    backend: AudioBackend | None = None,
) -> RetroAudio:
    """Create an audio stream via the given or process-wide registered backend.

    For GIL-free realtime playback from a PCM ring, prefer
    :func:`rwt_rconsole.pcm_ring.create_audio_from_ring` instead (pure-C
    AudioQueue callback; no Python on the audio thread).
    """
    factory = backend if backend is not None else get_audio_backend()
    if factory is None:
        raise RuntimeError(
            "No audio backend registered. Call "
            "rwt_rconsole.backends.apple_audio.register(), or pass backend=..."
        )
    return factory.create(config, callback)
