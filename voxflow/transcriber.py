"""faster-whisper transcription wrapper. Lazy-loads the model on first use."""
from __future__ import annotations

import logging
import threading
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

# Auto-detect the best compute_type for the device.
_CPU_COMPUTE_PREFERENCE = ["int8", "float32"]
_GPU_COMPUTE_PREFERENCE = ["float16", "int8_float16", "float32"]


class Transcriber:
    """Wraps faster-whisper.WhisperModel with lazy loading + reload-on-config-change."""

    def __init__(self, model_size: str, device: str, compute_type: str, language: str) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model = None
        self._lock = threading.Lock()

    def _resolve_device(self) -> str:
        if self.device != "auto":
            return self.device
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda"
        except Exception:  # noqa: BLE001
            pass
        return "cpu"

    def _resolve_compute_type(self, device: str) -> str:
        if self.compute_type != "auto":
            return self.compute_type
        return "float16" if device == "cuda" else "int8"

    def _load(self):
        from faster_whisper import WhisperModel

        device = self._resolve_device()
        compute_type = self._resolve_compute_type(device)
        preference = _GPU_COMPUTE_PREFERENCE if device == "cuda" else _CPU_COMPUTE_PREFERENCE
        ordered = [compute_type] + [c for c in preference if c != compute_type]

        last_err: Optional[Exception] = None
        for ct in ordered:
            try:
                log.info("Loading Whisper model '%s' on %s (%s)...", self.model_size, device, ct)
                return WhisperModel(self.model_size, device=device, compute_type=ct)
            except (ValueError, RuntimeError) as e:
                log.warning("compute_type=%s failed (%s), trying next...", ct, e)
                last_err = e
        raise RuntimeError(f"Could not load Whisper model: {last_err}")

    def ensure_loaded(self) -> None:
        with self._lock:
            if self._model is None:
                self._model = self._load()

    def update_config(self, model_size: str, device: str, compute_type: str, language: str) -> None:
        """If model-affecting settings changed, drop the model so it reloads next time."""
        reload = (
            model_size != self.model_size
            or device != self.device
            or compute_type != self.compute_type
        )
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        if reload:
            with self._lock:
                self._model = None
                log.info("Whisper config changed, will reload on next transcription")

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        if audio.size == 0:
            return ""
        if sample_rate != 16000:
            # faster-whisper expects 16 kHz mono float32
            raise ValueError(f"Expected 16kHz audio, got {sample_rate}Hz")
        return self._run(audio)

    def transcribe_file(self, path: str) -> str:
        """Transcribe an audio file from disk. faster-whisper handles decoding/resampling."""
        return self._run(path)

    def _run(self, source) -> str:
        self.ensure_loaded()
        assert self._model is not None
        lang = None if self.language == "auto" else self.language
        segments, info = self._model.transcribe(
            source,
            language=lang,
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=False,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        log.info("Transcribed (%s, %.2fs): %s", info.language, info.duration, text[:80])
        return text
