"""Keyboard and mouse input types and protocol."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RetroPoint:
    """Position in retro source pixel space (0..Width-1, 0..Height-1)."""

    x: int
    y: int


class MouseButton(IntEnum):
    LEFT = 0
    RIGHT = 1
    MIDDLE = 2
    OTHER = 3


class Key(IntEnum):
    """Keyboard keys matching standard physical/virtual key codes."""

    UNKNOWN = 0
    A = 1
    B = 2
    C = 3
    D = 4
    E = 5
    F = 6
    G = 7
    H = 8
    I = 9
    J = 10
    K = 11
    L = 12
    M = 13
    N = 14
    O = 15
    P = 16
    Q = 17
    R = 18
    S = 19
    T = 20
    U = 21
    V = 22
    W = 23
    X = 24
    Y = 25
    Z = 26
    D0 = 30
    D1 = 31
    D2 = 32
    D3 = 33
    D4 = 34
    D5 = 35
    D6 = 36
    D7 = 37
    D8 = 38
    D9 = 39
    RETURN = 40
    ESCAPE = 41
    BACKSPACE = 42
    TAB = 43
    SPACE = 44
    MINUS = 45
    EQUALS = 46
    LEFT_BRACKET = 47
    RIGHT_BRACKET = 48
    BACKSLASH = 49
    SEMICOLON = 50
    QUOTE = 51
    GRAVE = 52
    COMMA = 53
    PERIOD = 54
    SLASH = 55
    CAPS_LOCK = 57
    F1 = 58
    F2 = 59
    F3 = 60
    F4 = 61
    F5 = 62
    F6 = 63
    F7 = 64
    F8 = 65
    F9 = 66
    F10 = 67
    F11 = 68
    F12 = 69
    PRINT_SCREEN = 70
    SCROLL_LOCK = 71
    PAUSE = 72
    INSERT = 73
    HOME = 74
    PAGE_UP = 75
    DELETE = 76
    END = 77
    PAGE_DOWN = 78
    RIGHT = 79
    LEFT = 80
    DOWN = 81
    UP = 82
    NUM_LOCK = 83
    KEYPAD_DIVIDE = 84
    KEYPAD_MULTIPLY = 85
    KEYPAD_MINUS = 86
    KEYPAD_PLUS = 87
    KEYPAD_ENTER = 88
    KEYPAD_1 = 89
    KEYPAD_2 = 90
    KEYPAD_3 = 91
    KEYPAD_4 = 92
    KEYPAD_5 = 93
    KEYPAD_6 = 94
    KEYPAD_7 = 95
    KEYPAD_8 = 96
    KEYPAD_9 = 97
    KEYPAD_0 = 98
    KEYPAD_DECIMAL = 99
    LEFT_CTRL = 100
    LEFT_SHIFT = 101
    LEFT_ALT = 102
    LEFT_SUPER = 103
    RIGHT_CTRL = 104
    RIGHT_SHIFT = 105
    RIGHT_ALT = 106
    RIGHT_SUPER = 107


@dataclass(frozen=True, slots=True)
class MouseEventInfo:
    button: MouseButton
    retro_position: RetroPoint | None
    window_position: tuple[float, float]


@dataclass(frozen=True, slots=True)
class MouseMoveInfo:
    retro_position: RetroPoint | None
    window_position: tuple[float, float]


@runtime_checkable
class InputContext(Protocol):
    """Complete input state for keyboard and mouse polling."""

    def is_key_down(self, key: Key) -> bool: ...
    def is_key_pressed(self, key: Key) -> bool: ...
    def is_key_released(self, key: Key) -> bool: ...

    def is_mouse_button_down(self, button: MouseButton) -> bool: ...
    def is_mouse_button_pressed(self, button: MouseButton) -> bool: ...
    def is_mouse_button_released(self, button: MouseButton) -> bool: ...

    @property
    def mouse_position(self) -> RetroPoint | None: ...

    @property
    def mouse_delta(self) -> tuple[float, float]: ...

    @property
    def scroll_delta(self) -> float: ...


@dataclass
class NullInputContext:
    """No-op input context for headless / tests."""

    _mouse_position: RetroPoint | None = None
    _mouse_delta: tuple[float, float] = (0.0, 0.0)
    _scroll_delta: float = 0.0

    def is_key_down(self, key: Key) -> bool:
        return False

    def is_key_pressed(self, key: Key) -> bool:
        return False

    def is_key_released(self, key: Key) -> bool:
        return False

    def is_mouse_button_down(self, button: MouseButton) -> bool:
        return False

    def is_mouse_button_pressed(self, button: MouseButton) -> bool:
        return False

    def is_mouse_button_released(self, button: MouseButton) -> bool:
        return False

    @property
    def mouse_position(self) -> RetroPoint | None:
        return self._mouse_position

    @property
    def mouse_delta(self) -> tuple[float, float]:
        return self._mouse_delta

    @property
    def scroll_delta(self) -> float:
        return self._scroll_delta
