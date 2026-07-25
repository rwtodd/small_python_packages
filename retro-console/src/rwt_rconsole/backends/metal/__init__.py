"""macOS Metal display backend (optional dependency: rwt-rconsole[metal])."""

from __future__ import annotations


def register() -> None:
    """Register the Metal display backend as the process-wide factory."""
    from rwt_rconsole.display import register_display_backend

    from .display import MetalDisplayBackend

    register_display_backend(MetalDisplayBackend())


__all__ = ["register"]
