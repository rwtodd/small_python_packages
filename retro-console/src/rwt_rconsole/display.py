"""Display creation, backend registration, and protocols."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from .framebuffer import FrameBuffer
from .input import InputContext
from .memory import Palette
from .types import DisplayConfig, FrameTickResult

FrameCallbackResult = FrameTickResult | bool


def should_present(result: FrameCallbackResult) -> bool:
    """Interpret a frame-callback return value: True/PRESENT → present."""
    if isinstance(result, FrameTickResult):
        return result is FrameTickResult.PRESENT
    return bool(result)


@runtime_checkable
class RetroDisplay(Protocol):
    """Platform-agnostic display: framebuffer, palette, and present/run loop."""

    @property
    def config(self) -> DisplayConfig: ...

    @property
    def buffer(self) -> FrameBuffer: ...

    @property
    def palette(self) -> Palette: ...

    @property
    def input(self) -> InputContext: ...

    def present(self) -> None: ...

    def run(
        self,
        fps: float,
        on_frame: Callable[[RetroDisplay], FrameCallbackResult],
        *,
        cancel: Callable[[], bool] | None = None,
    ) -> None: ...

    def poll_events(self) -> bool: ...

    def close(self) -> None: ...

    def __enter__(self) -> RetroDisplay: ...

    def __exit__(self, *exc: object) -> None: ...


class DisplayBackend(Protocol):
    def create(self, config: DisplayConfig) -> RetroDisplay: ...


_display_backend: DisplayBackend | None = None
_display_lock = threading.Lock()


def register_display_backend(backend: DisplayBackend) -> None:
    """Register the process-wide display backend (e.g. Metal)."""
    with _display_lock:
        global _display_backend
        _display_backend = backend


def clear_display_backend() -> None:
    """Clear the registered display backend (mainly for tests)."""
    with _display_lock:
        global _display_backend
        _display_backend = None


def get_display_backend() -> DisplayBackend | None:
    with _display_lock:
        return _display_backend


def create_display(
    config: DisplayConfig,
    *,
    backend: DisplayBackend | None = None,
) -> RetroDisplay:
    """Create a display via the given or process-wide registered backend.

    *config* is validated by ``DisplayConfig`` itself on construction.
    """
    factory = backend if backend is not None else get_display_backend()
    if factory is None:
        raise RuntimeError(
            "No display backend registered. Install the metal extra and call "
            "rwt_rconsole.backends.metal.register(), or pass backend=..."
        )
    return factory.create(config)
