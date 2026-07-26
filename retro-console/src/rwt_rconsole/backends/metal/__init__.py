"""macOS Metal display backend (optional dependency: rwt-rconsole[metal])."""

from __future__ import annotations


def register() -> None:
    """Register the Metal display backend as the process-wide factory."""
    from rwt_rconsole.display import register_display_backend

    from .display import MetalDisplayBackend

    register_display_backend(MetalDisplayBackend())


def main_display_refresh_rate() -> float:
    """Nominal refresh rate of the main display in Hz (0.0 if unknown)."""
    from .display import main_display_refresh_rate as _impl

    return _impl()


__all__ = ["register", "main_display_refresh_rate"]
