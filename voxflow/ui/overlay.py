"""Always-on-top overlay window showing live audio waveform + partial transcript.

Runs on its own thread with its own tkinter root. Main app pushes updates via
thread-safe calls; the overlay polls them via `.after()` from its own event loop.
"""
from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

# Tunables
WAVEFORM_BARS = 28
WAVEFORM_HISTORY = 28
BAR_WIDTH = 4
BAR_GAP = 3
WINDOW_WIDTH = 340
WINDOW_HEIGHT = 110
BG = "#111418"
FG = "#e9edf1"
ACCENT_IDLE = "#4a90e2"
ACCENT_REC = "#ff4a5c"
ACCENT_BUSY = "#f5a623"
ACCENT_DONE = "#4ade80"


@dataclass
class _Msg:
    kind: str                  # "level" | "status" | "partial" | "final" | "close" | "color"
    value: object = None


class Overlay:
    """Thread-safe overlay handle. The window runs in a background thread."""

    def __init__(self) -> None:
        self._q: "queue.Queue[_Msg]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._alive = threading.Event()

    # ---- public (main-thread safe) ----
    def show(self) -> None:
        if self._alive.is_set():
            return
        self._alive.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def hide(self) -> None:
        if not self._alive.is_set():
            return
        self._q.put(_Msg("close"))
        self._alive.clear()

    def is_open(self) -> bool:
        return self._alive.is_set()

    def set_level(self, rms: float) -> None:
        self._q.put(_Msg("level", max(0.0, min(1.0, float(rms)))))

    def set_status(self, text: str, color: str = ACCENT_IDLE) -> None:
        self._q.put(_Msg("status", (text, color)))

    def set_partial(self, text: str) -> None:
        self._q.put(_Msg("partial", text or ""))

    def set_final(self, text: str) -> None:
        self._q.put(_Msg("final", text or ""))

    # ---- window thread ----
    def _run(self) -> None:
        try:
            self._build()
            self._poll()
            self._root.mainloop()
        except Exception as e:  # noqa: BLE001
            log.warning("Overlay crashed: %s", e)
        finally:
            self._alive.clear()

    def _build(self) -> None:
        self._root = tk.Tk()
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        try:
            self._root.attributes("-alpha", 0.94)
        except tk.TclError:
            pass
        self._root.configure(bg=BG)

        # Position bottom-center of primary screen.
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = (sw - WINDOW_WIDTH) // 2
        y = sh - WINDOW_HEIGHT - 80
        self._root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

        # Rounded-looking container using a single frame (tkinter can't do true rounded)
        container = tk.Frame(self._root, bg=BG, padx=14, pady=10)
        container.pack(fill="both", expand=True)

        top = tk.Frame(container, bg=BG)
        top.pack(fill="x")
        self._dot = tk.Canvas(top, width=12, height=12, bg=BG, highlightthickness=0)
        self._dot.pack(side="left")
        self._dot_id = self._dot.create_oval(2, 2, 10, 10, fill=ACCENT_REC, outline="")
        self._status_var = tk.StringVar(value="Listening...")
        tk.Label(
            top, textvariable=self._status_var, fg=FG, bg=BG,
            font=("Helvetica", 11, "bold"),
        ).pack(side="left", padx=8)

        # Waveform canvas
        self._canvas = tk.Canvas(
            container, width=WAVEFORM_BARS * (BAR_WIDTH + BAR_GAP),
            height=32, bg=BG, highlightthickness=0,
        )
        self._canvas.pack(pady=(6, 6))
        self._levels: list[float] = [0.0] * WAVEFORM_HISTORY
        self._bars = []
        for i in range(WAVEFORM_BARS):
            x0 = i * (BAR_WIDTH + BAR_GAP)
            self._bars.append(
                self._canvas.create_rectangle(
                    x0, 16, x0 + BAR_WIDTH, 18, fill=ACCENT_REC, outline=""
                )
            )

        # Transcript label (partial / final)
        self._text_var = tk.StringVar(value="")
        tk.Label(
            container, textvariable=self._text_var, fg="#9aa5b1", bg=BG,
            font=("Helvetica", 10), wraplength=WINDOW_WIDTH - 28, justify="left",
            anchor="w",
        ).pack(fill="x")

        # Pulse animation state
        self._pulse_on = True
        self._current_color = ACCENT_REC
        self._root.after(500, self._pulse)

    def _pulse(self) -> None:
        if not self._alive.is_set():
            return
        self._pulse_on = not self._pulse_on
        self._dot.itemconfigure(
            self._dot_id,
            fill=self._current_color if self._pulse_on else BG,
        )
        self._root.after(500, self._pulse)

    def _poll(self) -> None:
        try:
            while True:
                msg = self._q.get_nowait()
                self._apply(msg)
                if msg.kind == "close":
                    return
        except queue.Empty:
            pass
        self._root.after(30, self._poll)

    def _apply(self, msg: _Msg) -> None:
        if msg.kind == "close":
            try:
                self._root.destroy()
            except tk.TclError:
                pass
            return
        if msg.kind == "level":
            self._push_level(float(msg.value))  # type: ignore[arg-type]
        elif msg.kind == "status":
            text, color = msg.value  # type: ignore[misc]
            self._status_var.set(text)
            self._current_color = color
            self._recolor_bars(color)
        elif msg.kind == "partial":
            self._text_var.set(str(msg.value))
        elif msg.kind == "final":
            self._text_var.set(str(msg.value))
            # Auto-close after a short moment so users see the result.
            self._root.after(1500, lambda: self._q.put(_Msg("close")))

    def _push_level(self, rms: float) -> None:
        # Log-ish scaling so quiet speech still shows.
        lvl = min(1.0, rms * 6.0)
        self._levels.pop(0)
        self._levels.append(lvl)
        height = 28
        base_y = 16
        for i, bar in enumerate(self._bars):
            h = max(1, int(self._levels[i] * height))
            x0 = i * (BAR_WIDTH + BAR_GAP)
            self._canvas.coords(bar, x0, base_y - h // 2, x0 + BAR_WIDTH, base_y + h // 2)

    def _recolor_bars(self, color: str) -> None:
        for bar in self._bars:
            self._canvas.itemconfigure(bar, fill=color)
