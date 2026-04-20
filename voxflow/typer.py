"""Output text: auto-type at cursor, or copy to clipboard."""
from __future__ import annotations

import logging
import time

import pyperclip
from pynput.keyboard import Controller

log = logging.getLogger(__name__)


class TextOutput:
    def __init__(self, type_delay_ms: int = 5) -> None:
        self.type_delay_ms = type_delay_ms
        self._kb = Controller()

    def output(self, text: str, mode: str) -> None:
        if not text:
            return
        if mode == "clipboard":
            self._copy(text)
        else:
            self._type(text)

    def _copy(self, text: str) -> None:
        try:
            pyperclip.copy(text)
            log.info("Copied %d chars to clipboard", len(text))
        except Exception as e:  # noqa: BLE001
            log.error("Clipboard copy failed: %s", e)

    def _type(self, text: str) -> None:
        try:
            delay = max(0.0, self.type_delay_ms / 1000.0)
            for ch in text:
                self._kb.type(ch)
                if delay:
                    time.sleep(delay)
            log.info("Typed %d chars", len(text))
        except Exception as e:  # noqa: BLE001
            log.error("Auto-type failed (%s). Falling back to clipboard.", e)
            self._copy(text)
