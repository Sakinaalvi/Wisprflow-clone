"""Main VoxFlow app controller: wires hotkey -> record -> transcribe -> post-process -> output.
Runs a system tray icon on the main thread.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from PIL import Image, ImageDraw
import pystray

from voxflow.config import Config, HISTORY_PATH
from voxflow.history import History
from voxflow.hotkeys import HotkeyManager
from voxflow.post_processor import PostProcessor
from voxflow.recorder import Recorder
from voxflow.transcriber import Transcriber
from voxflow.typer import TextOutput
from voxflow.ui.overlay import (
    ACCENT_BUSY, ACCENT_DONE, ACCENT_REC, Overlay,
)

log = logging.getLogger(__name__)


def _make_icon(color: str) -> Image.Image:
    """Programmatic 64x64 tray icon — a colored mic glyph."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # mic body
    d.rounded_rectangle([22, 10, 42, 38], radius=10, fill=color)
    # stand
    d.rectangle([30, 46, 34, 56], fill=color)
    d.rectangle([20, 54, 44, 58], fill=color)
    # arc
    d.arc([16, 22, 48, 50], start=0, end=180, fill=color, width=3)
    return img


class VoxFlowApp:
    IDLE_COLOR = "#4a90e2"
    REC_COLOR = "#e24a4a"
    BUSY_COLOR = "#f5a623"

    def __init__(self) -> None:
        self.config = Config.load()
        self.recorder = Recorder(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
        )
        self.transcriber = Transcriber(
            model_size=self.config.model_size,
            device=self.config.device,
            compute_type=self.config.compute_type,
            language=self.config.language,
        )
        self.post_processor = PostProcessor(
            voice_commands_enabled=self.config.voice_commands_enabled,
            custom_replacements=self.config.custom_replacements,
            strip_filler_words=self.config.strip_filler_words,
            ai_enabled=self.config.ai_enabled,
            ai_provider=self.config.ai_provider,
            ollama_model=self.config.ollama_model,
            ollama_url=self.config.ollama_url,
        )
        self.text_output = TextOutput(type_delay_ms=self.config.type_delay_ms)
        self.history = History(HISTORY_PATH)

        self.hotkeys: Optional[HotkeyManager] = None
        self.tray: Optional[pystray.Icon] = None
        self.overlay = Overlay()

        self._busy = threading.Lock()
        self._record_started_at: float = 0.0
        self._live_stop = threading.Event()
        self._live_thread: Optional[threading.Thread] = None
        self._latest_partial: str = ""

    # ------- lifecycle -------
    def run(self) -> None:
        self._start_hotkeys()
        # Warm up the model in a background thread so the first hotkey press is snappy.
        threading.Thread(target=self._warmup, daemon=True).start()
        self._run_tray()  # blocks

    def shutdown(self) -> None:
        log.info("Shutting down...")
        if self.hotkeys:
            self.hotkeys.stop()
        self._live_stop.set()
        self.overlay.hide()
        self.recorder.cancel()
        self.history.close()
        if self.tray:
            self.tray.stop()

    def _warmup(self) -> None:
        try:
            self.transcriber.ensure_loaded()
        except Exception as e:  # noqa: BLE001
            log.error("Warmup failed: %s", e)

    # ------- hotkey pipeline -------
    def _start_hotkeys(self) -> None:
        if self.hotkeys:
            self.hotkeys.stop()
        self.hotkeys = HotkeyManager(
            hotkey=self.config.hotkey,
            push_to_talk=self.config.push_to_talk,
            on_start=self._on_record_start,
            on_stop=self._on_record_stop,
        )
        self.hotkeys.start()

    def _on_record_start(self) -> None:
        if self.recorder.is_recording:
            return
        self._record_started_at = time.time()
        self._latest_partial = ""
        self.recorder.start()
        self._set_tray_icon(self.REC_COLOR, "VoxFlow — recording...")
        if self.config.overlay_enabled:
            self.overlay.show()
            self.overlay.set_status("Listening...", ACCENT_REC)
            self.overlay.set_partial("")
            self._start_live_worker()

    def _on_record_stop(self) -> None:
        if not self.recorder.is_recording:
            return
        duration = time.time() - self._record_started_at
        self._live_stop.set()
        audio = self.recorder.stop()
        self._set_tray_icon(self.BUSY_COLOR, "VoxFlow — transcribing...")
        if duration < self.config.min_record_seconds or audio.size == 0:
            log.info("Ignoring short recording (%.2fs)", duration)
            self._set_tray_icon(self.IDLE_COLOR, "VoxFlow — idle")
            self.overlay.hide()
            return
        if self.config.overlay_enabled:
            self.overlay.set_status("Transcribing...", ACCENT_BUSY)
        threading.Thread(
            target=self._transcribe_and_output,
            args=(audio, duration),
            daemon=True,
        ).start()

    def _start_live_worker(self) -> None:
        """Background thread: push RMS to overlay at ~30Hz, kick partial transcripts periodically."""
        self._live_stop.clear()

        def worker() -> None:
            last_partial = 0.0
            while not self._live_stop.is_set() and self.recorder.is_recording:
                # Waveform tick
                try:
                    rms = self.recorder.peek_rms()
                    self.overlay.set_level(rms)
                except Exception:  # noqa: BLE001
                    pass

                # Partial transcript tick
                now = time.time()
                if (
                    self.config.show_partial_transcripts
                    and now - last_partial >= self.config.partial_interval_s
                ):
                    last_partial = now
                    audio = self.recorder.peek_audio()
                    # Need at least ~0.8s of audio before first partial
                    if audio.size >= int(self.config.sample_rate * 0.8):
                        threading.Thread(
                            target=self._run_partial, args=(audio,), daemon=True,
                        ).start()

                time.sleep(0.03)

        self._live_thread = threading.Thread(target=worker, daemon=True)
        self._live_thread.start()

    def _run_partial(self, audio) -> None:
        try:
            text = self.transcriber.transcribe_partial(audio, self.config.sample_rate)
            if text:
                self._latest_partial = text
                self.overlay.set_partial(text)
        except Exception as e:  # noqa: BLE001
            log.debug("Partial run failed: %s", e)

    def _transcribe_and_output(self, audio, duration: float) -> None:
        with self._busy:
            try:
                raw = self.transcriber.transcribe(audio, self.config.sample_rate)
                final = self.post_processor.process(raw)
                if final:
                    self.text_output.output(final, mode=self.config.output_mode)
                    self.history.add(
                        raw_text=raw,
                        final_text=final,
                        language=self.config.language,
                        duration_s=duration,
                    )
                    if self.config.overlay_enabled:
                        self.overlay.set_status("Done", ACCENT_DONE)
                        preview = final if len(final) <= 140 else final[:137] + "..."
                        self.overlay.set_final(preview)
                else:
                    self.overlay.hide()
            except Exception as e:  # noqa: BLE001
                log.exception("Transcription pipeline failed: %s", e)
                self.overlay.hide()
            finally:
                self._set_tray_icon(self.IDLE_COLOR, "VoxFlow — idle")

    # ------- tray -------
    def _run_tray(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("Settings...", self._open_settings),
            pystray.MenuItem("History...", self._open_history),
            pystray.MenuItem(
                "Output mode",
                pystray.Menu(
                    pystray.MenuItem(
                        "Auto-type",
                        self._set_output_type,
                        checked=lambda i: self.config.output_mode == "type",
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Clipboard",
                        self._set_output_clipboard,
                        checked=lambda i: self.config.output_mode == "clipboard",
                        radio=True,
                    ),
                ),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )
        self.tray = pystray.Icon(
            "voxflow",
            _make_icon(self.IDLE_COLOR),
            "VoxFlow — idle",
            menu=menu,
        )
        self.tray.run()

    def _set_tray_icon(self, color: str, tooltip: str) -> None:
        if self.tray is not None:
            try:
                self.tray.icon = _make_icon(color)
                self.tray.title = tooltip
            except Exception:  # noqa: BLE001
                pass

    # ------- menu handlers -------
    def _set_output_type(self, _icon, _item) -> None:
        self.config.output_mode = "type"
        self.config.save()

    def _set_output_clipboard(self, _icon, _item) -> None:
        self.config.output_mode = "clipboard"
        self.config.save()

    def _open_settings(self, _icon=None, _item=None) -> None:
        from voxflow.ui.settings_window import SettingsWindow
        SettingsWindow(self.config, on_save=self._on_config_saved).show()

    def _open_history(self, _icon=None, _item=None) -> None:
        from voxflow.ui.history_window import HistoryWindow
        HistoryWindow(self.history).show()

    def _on_config_saved(self) -> None:
        """Apply live config changes without restarting."""
        self.config.save()
        self.transcriber.update_config(
            model_size=self.config.model_size,
            device=self.config.device,
            compute_type=self.config.compute_type,
            language=self.config.language,
        )
        self.post_processor.update(
            voice_commands_enabled=self.config.voice_commands_enabled,
            custom_replacements=self.config.custom_replacements,
            strip_filler_words=self.config.strip_filler_words,
            ai_enabled=self.config.ai_enabled,
            ai_provider=self.config.ai_provider,
            ollama_model=self.config.ollama_model,
            ollama_url=self.config.ollama_url,
        )
        self.text_output.type_delay_ms = self.config.type_delay_ms
        self.recorder = Recorder(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
        )
        self._start_hotkeys()
        log.info("Config reloaded")

    def _quit(self, _icon=None, _item=None) -> None:
        self.shutdown()
