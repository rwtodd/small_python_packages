"""macOS virtual key code → Key mapping and Metal input state."""

from __future__ import annotations

import threading
from collections.abc import Callable

from rwt_rconsole.input import (
    Key,
    MouseButton,
    MouseEventInfo,
    MouseMoveInfo,
    RetroPoint,
)
from rwt_rconsole.types import DisplayConfig
from rwt_rconsole.video_math import screen_to_source

# macOS NSEvent keyCode → Key
_MAC_KEY_MAP: dict[int, Key] = {
    0: Key.A,
    1: Key.S,
    2: Key.D,
    3: Key.F,
    4: Key.H,
    5: Key.G,
    6: Key.Z,
    7: Key.X,
    8: Key.C,
    9: Key.V,
    11: Key.B,
    12: Key.Q,
    13: Key.W,
    14: Key.E,
    15: Key.R,
    16: Key.Y,
    17: Key.T,
    18: Key.D1,
    19: Key.D2,
    20: Key.D3,
    21: Key.D4,
    22: Key.D6,
    23: Key.D5,
    24: Key.EQUALS,
    25: Key.D9,
    26: Key.D7,
    27: Key.MINUS,
    28: Key.D8,
    29: Key.D0,
    30: Key.RIGHT_BRACKET,
    31: Key.O,
    32: Key.U,
    33: Key.LEFT_BRACKET,
    34: Key.I,
    35: Key.P,
    36: Key.RETURN,
    37: Key.L,
    38: Key.J,
    39: Key.QUOTE,
    40: Key.K,
    41: Key.SEMICOLON,
    42: Key.BACKSLASH,
    43: Key.COMMA,
    44: Key.SLASH,
    45: Key.N,
    46: Key.M,
    47: Key.PERIOD,
    48: Key.TAB,
    49: Key.SPACE,
    50: Key.GRAVE,
    51: Key.BACKSPACE,
    53: Key.ESCAPE,
    54: Key.RIGHT_SUPER,
    55: Key.LEFT_SUPER,
    56: Key.LEFT_SHIFT,
    57: Key.CAPS_LOCK,
    58: Key.LEFT_ALT,
    59: Key.LEFT_CTRL,
    60: Key.RIGHT_SHIFT,
    61: Key.RIGHT_ALT,
    62: Key.RIGHT_CTRL,
    65: Key.KEYPAD_DECIMAL,
    67: Key.KEYPAD_MULTIPLY,
    69: Key.KEYPAD_PLUS,
    71: Key.NUM_LOCK,
    75: Key.KEYPAD_DIVIDE,
    76: Key.KEYPAD_ENTER,
    78: Key.KEYPAD_MINUS,
    82: Key.KEYPAD_0,
    83: Key.KEYPAD_1,
    84: Key.KEYPAD_2,
    85: Key.KEYPAD_3,
    86: Key.KEYPAD_4,
    87: Key.KEYPAD_5,
    88: Key.KEYPAD_6,
    89: Key.KEYPAD_7,
    91: Key.KEYPAD_8,
    92: Key.KEYPAD_9,
    96: Key.F5,
    97: Key.F6,
    98: Key.F7,
    99: Key.F3,
    100: Key.F8,
    101: Key.F9,
    109: Key.F10,
    111: Key.F12,
    114: Key.INSERT,
    115: Key.HOME,
    116: Key.PAGE_UP,
    117: Key.DELETE,
    118: Key.F4,
    119: Key.END,
    120: Key.F2,
    121: Key.PAGE_DOWN,
    122: Key.F1,
    123: Key.LEFT,
    124: Key.RIGHT,
    125: Key.DOWN,
    126: Key.UP,
}


def map_key(key_code: int) -> Key:
    return _MAC_KEY_MAP.get(int(key_code), Key.UNKNOWN)


class MetalInput:
    """Keyboard/mouse state for a Metal display."""

    def __init__(self, config: DisplayConfig) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._keys_down: set[Key] = set()
        self._prev_keys_down: set[Key] = set()
        self._buttons_down: set[MouseButton] = set()
        self._prev_buttons_down: set[MouseButton] = set()
        self._mouse_position: RetroPoint | None = None
        self._last_win_pt: tuple[float, float] | None = None
        self._mouse_delta = (0.0, 0.0)
        self._scroll_delta = 0.0

        self.on_key_down: list[Callable[[Key], None]] = []
        self.on_key_up: list[Callable[[Key], None]] = []
        self.on_text_input: list[Callable[[str], None]] = []
        self.on_mouse_down: list[Callable[[MouseEventInfo], None]] = []
        self.on_mouse_up: list[Callable[[MouseEventInfo], None]] = []
        self.on_mouse_move: list[Callable[[MouseMoveInfo], None]] = []

    def update_frame_state(self) -> None:
        with self._lock:
            self._prev_keys_down = set(self._keys_down)
            self._prev_buttons_down = set(self._buttons_down)
            self._mouse_delta = (0.0, 0.0)
            self._scroll_delta = 0.0

    def process_key_down(self, key_code: int, characters: str | None) -> None:
        key = map_key(key_code)
        is_new = False
        with self._lock:
            if key not in self._keys_down:
                self._keys_down.add(key)
                is_new = True
        if is_new:
            for cb in self.on_key_down:
                cb(key)
        if characters:
            for ch in characters:
                if not ch.isprintable():
                    continue
                for cb in self.on_text_input:
                    cb(ch)

    def process_key_up(self, key_code: int) -> None:
        key = map_key(key_code)
        removed = False
        with self._lock:
            if key in self._keys_down:
                self._keys_down.discard(key)
                removed = True
        if removed:
            for cb in self.on_key_up:
                cb(key)

    def process_flags_changed(self, key_code: int, flags: int, mask_for_key: int | None) -> None:
        key = map_key(key_code)
        if key is Key.UNKNOWN or mask_for_key is None:
            return
        is_flag_active = bool(flags & mask_for_key)
        with self._lock:
            was_down = key in self._keys_down
            if is_flag_active and not was_down:
                self._keys_down.add(key)
                trigger_down = True
                trigger_up = False
            elif not is_flag_active and was_down:
                self._keys_down.discard(key)
                trigger_down = False
                trigger_up = True
            else:
                trigger_down = trigger_up = False
        if trigger_down:
            for cb in self.on_key_down:
                cb(key)
        if trigger_up:
            for cb in self.on_key_up:
                cb(key)

    def process_mouse_down(
        self, button: MouseButton, view_size: tuple[float, float], win_pt: tuple[float, float]
    ) -> None:
        with self._lock:
            self._buttons_down.add(button)
        retro = screen_to_source(self._config, view_size, win_pt)
        self._mouse_position = retro
        info = MouseEventInfo(button, retro, win_pt)
        for cb in self.on_mouse_down:
            cb(info)

    def process_mouse_up(
        self, button: MouseButton, view_size: tuple[float, float], win_pt: tuple[float, float]
    ) -> None:
        with self._lock:
            self._buttons_down.discard(button)
        retro = screen_to_source(self._config, view_size, win_pt)
        self._mouse_position = retro
        info = MouseEventInfo(button, retro, win_pt)
        for cb in self.on_mouse_up:
            cb(info)

    def process_mouse_move(
        self, view_size: tuple[float, float], win_pt: tuple[float, float]
    ) -> None:
        px, py = win_pt
        if self._last_win_pt is not None:
            lx, ly = self._last_win_pt
            dx, dy = self._mouse_delta
            self._mouse_delta = (dx + (px - lx), dy + (py - ly))
        self._last_win_pt = win_pt
        retro = screen_to_source(self._config, view_size, win_pt)
        self._mouse_position = retro
        info = MouseMoveInfo(retro, win_pt)
        for cb in self.on_mouse_move:
            cb(info)

    def process_scroll(self, delta_y: float) -> None:
        self._scroll_delta += delta_y

    def is_key_down(self, key: Key) -> bool:
        with self._lock:
            return key in self._keys_down

    def is_key_pressed(self, key: Key) -> bool:
        with self._lock:
            return key in self._keys_down and key not in self._prev_keys_down

    def is_key_released(self, key: Key) -> bool:
        with self._lock:
            return key not in self._keys_down and key in self._prev_keys_down

    def is_mouse_button_down(self, button: MouseButton) -> bool:
        with self._lock:
            return button in self._buttons_down

    def is_mouse_button_pressed(self, button: MouseButton) -> bool:
        with self._lock:
            return button in self._buttons_down and button not in self._prev_buttons_down

    def is_mouse_button_released(self, button: MouseButton) -> bool:
        with self._lock:
            return button not in self._buttons_down and button in self._prev_buttons_down

    @property
    def mouse_position(self) -> RetroPoint | None:
        return self._mouse_position

    @property
    def mouse_delta(self) -> tuple[float, float]:
        return self._mouse_delta

    @property
    def scroll_delta(self) -> float:
        return self._scroll_delta
