"""Global hotkey manager using pynput. Supports push-to-talk (hold) and toggle (tap)."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from pynput import keyboard

log = logging.getLogger(__name__)

# Friendly-name -> pynput Key mapping for common single keys.
SPECIAL_KEYS = {
    "right_ctrl": keyboard.Key.ctrl_r,
    "left_ctrl": keyboard.Key.ctrl_l,
    "right_alt": keyboard.Key.alt_r,
    "left_alt": keyboard.Key.alt_l,
    "right_shift": keyboard.Key.shift_r,
    "left_shift": keyboard.Key.shift_l,
    "right_cmd": keyboard.Key.cmd_r,
    "left_cmd": keyboard.Key.cmd_l,
    "caps_lock": keyboard.Key.caps_lock,
    "space": keyboard.Key.space,
    "tab": keyboard.Key.tab,
    "esc": keyboard.Key.esc,
    "f1": keyboard.Key.f1, "f2": keyboard.Key.f2, "f3": keyboard.Key.f3,
    "f4": keyboard.Key.f4, "f5": keyboard.Key.f5, "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7, "f8": keyboard.Key.f8, "f9": keyboard.Key.f9,
    "f10": keyboard.Key.f10, "f11": keyboard.Key.f11, "f12": keyboard.Key.f12,
}


def _parse_single(name: str):
    """Resolve a single key name to a pynput Key or KeyCode."""
    name = name.strip().lower()
    if name in SPECIAL_KEYS:
        return SPECIAL_KEYS[name]
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    raise ValueError(f"Unknown key: {name}")


class HotkeyManager:
    """
    Supports either:
      - A single key (e.g. "right_ctrl") — listens for hold/release directly.
      - A combo (e.g. "ctrl+alt+space") — uses pynput GlobalHotKeys for press,
        plus a release listener for push-to-talk semantics.

    Modes:
      - push_to_talk=True: on_press starts recording, on_release stops.
      - push_to_talk=False: on_press toggles (start/stop).
    """

    def __init__(
        self,
        hotkey: str,
        push_to_talk: bool,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
    ) -> None:
        self.hotkey = hotkey
        self.push_to_talk = push_to_talk
        self.on_start = on_start
        self.on_stop = on_stop

        self._listener: Optional[keyboard.Listener] = None
        self._combo_listener: Optional[keyboard.GlobalHotKeys] = None
        self._is_combo = "+" in hotkey
        self._target_key = None
        self._is_down = False
        self._toggled_on = False

    def start(self) -> None:
        if self._is_combo:
            self._start_combo()
        else:
            self._start_single()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        if self._combo_listener is not None:
            self._combo_listener.stop()
            self._combo_listener = None

    # --- single-key path ---
    def _start_single(self) -> None:
        try:
            self._target_key = _parse_single(self.hotkey)
        except ValueError as e:
            log.error("Invalid hotkey '%s': %s", self.hotkey, e)
            return

        def on_press(key):
            if not self._matches(key):
                return
            if self.push_to_talk:
                if not self._is_down:
                    self._is_down = True
                    self._safe(self.on_start)
            else:
                # toggle mode fires on press
                if not self._is_down:
                    self._is_down = True
                    self._toggled_on = not self._toggled_on
                    if self._toggled_on:
                        self._safe(self.on_start)
                    else:
                        self._safe(self.on_stop)

        def on_release(key):
            if not self._matches(key):
                return
            self._is_down = False
            if self.push_to_talk:
                self._safe(self.on_stop)

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()
        log.info("Hotkey listener started: %s (push_to_talk=%s)", self.hotkey, self.push_to_talk)

    def _matches(self, key) -> bool:
        try:
            if isinstance(self._target_key, keyboard.Key):
                return key == self._target_key
            if isinstance(self._target_key, keyboard.KeyCode) and isinstance(key, keyboard.KeyCode):
                return key.char == self._target_key.char
        except AttributeError:
            return False
        return False

    # --- combo path ---
    def _start_combo(self) -> None:
        hk = self._translate_combo(self.hotkey)

        def on_activate():
            # For combos we only support toggle (press-to-toggle) cleanly.
            if not self._is_down:
                self._is_down = True
                self._toggled_on = not self._toggled_on
                if self._toggled_on:
                    self._safe(self.on_start)
                else:
                    self._safe(self.on_stop)

        # Track release of ANY of the combo keys to reset _is_down
        def on_release(_key):
            self._is_down = False

        self._combo_listener = keyboard.GlobalHotKeys({hk: on_activate})
        self._combo_listener.start()

        self._listener = keyboard.Listener(on_release=on_release)
        self._listener.start()
        log.info("Hotkey combo listener started: %s (toggle mode)", self.hotkey)

    @staticmethod
    def _translate_combo(combo: str) -> str:
        # e.g. "ctrl+alt+space" -> "<ctrl>+<alt>+<space>"
        parts = [p.strip().lower() for p in combo.split("+")]
        out: list[str] = []
        specials = {"ctrl", "alt", "shift", "cmd", "space", "tab", "esc",
                    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9",
                    "f10", "f11", "f12"}
        for p in parts:
            out.append(f"<{p}>" if p in specials else p)
        return "+".join(out)

    @staticmethod
    def _safe(fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            log.exception("Hotkey callback raised: %s", e)
