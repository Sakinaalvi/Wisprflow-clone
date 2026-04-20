"""Microphone capture using sounddevice. Buffers audio while recording, returns float32 numpy array."""
from __future__ import annotations

import logging
import threading
from typing import Optional

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)


class Recorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._stream: Optional[sd.InputStream] = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        if status:
            log.debug("Sounddevice status: %s", status)
        with self._lock:
            self._chunks.append(indata.copy())

    def start(self) -> None:
        if self._recording:
            return
        with self._lock:
            self._chunks = []
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
            self._recording = True
            log.info("Recording started")
        except Exception as e:
            log.error("Failed to start recording: %s", e)
            self._stream = None

    def stop(self) -> np.ndarray:
        if not self._recording:
            return np.zeros(0, dtype=np.float32)
        self._recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:  # noqa: BLE001
                log.warning("Error stopping stream: %s", e)
            self._stream = None
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._chunks, axis=0).flatten().astype(np.float32)
            self._chunks = []
        log.info("Recording stopped: %.2fs", len(audio) / self.sample_rate)
        return audio

    def cancel(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:  # noqa: BLE001
                pass
        self._stream = None
        self._recording = False
        with self._lock:
            self._chunks = []

    # ---- read-only peeks used by the live overlay ----
    def peek_audio(self) -> np.ndarray:
        """Return a copy of the buffered audio so far, without stopping."""
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self._chunks, axis=0).flatten().astype(np.float32)

    def peek_rms(self, window_chunks: int = 3) -> float:
        """RMS of the last few frames for a level meter."""
        with self._lock:
            if not self._chunks:
                return 0.0
            recent = self._chunks[-window_chunks:]
            arr = np.concatenate(recent, axis=0).flatten()
        if arr.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))
