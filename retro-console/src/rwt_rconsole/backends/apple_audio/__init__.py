"""macOS AudioQueue streaming backend (stdlib ctypes only)."""

from __future__ import annotations


def register() -> None:
    """Register the Apple Audio backend as the process-wide factory."""
    from rwt_rconsole.audio import (
        AudioChannels,
        AudioConfig,
        AudioSampleFormat,
        register_audio_backend,
    )

    from .device import AppleAudio

    class _Backend:
        def suggested_config(self) -> AudioConfig:
            return AudioConfig(
                sample_rate=44100,
                channels=AudioChannels.STEREO,
                format=AudioSampleFormat.FLOAT32,
                reverb=0,
            )

        def create(self, config, callback):
            return AppleAudio(config, callback)

    register_audio_backend(_Backend())


__all__ = ["register"]
