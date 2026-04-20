"""Transcription backends.

Two backends are supported, selected by Config.transcription_backend:
  - "local"  — faster-whisper (offline, GPU-accel, free)
  - "openai" — OpenAI Whisper API (cloud, requires API key)

A unified `Transcriber` class picks the backend at call time so the user can
switch on the fly from Settings without restarting the app.

Partial transcription (for the live overlay) is ONLY done with the local
backend — hitting the cloud API every 1.5s would be slow and expensive.
"""
from __future__ import annotations

import io
import logging
import os
import threading
import wave
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

_CPU_COMPUTE_PREFERENCE = ["int8", "float32"]
_GPU_COMPUTE_PREFERENCE = ["float16", "int8_float16", "float32"]


class Transcriber:
    def __init__(
        self,
        backend: str = "local",
        # local
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        # openai
        openai_whisper_model: str = "whisper-1",
        openai_api_key: str = "",
        # shared
        language: str = "auto",
    ) -> None:
        self.backend = backend
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.openai_whisper_model = openai_whisper_model
        self.openai_api_key = openai_api_key
        self.language = language

        self._local_model = None
        self._local_lock = threading.Lock()
        self._inference_lock = threading.Lock()
        self._openai_client = None

    # ---- config updates ----
    def update_config(self, **kwargs) -> None:
        """Apply a set of updates. Reloads the local model if relevant fields changed."""
        reload_local = False
        for key in ("model_size", "device", "compute_type"):
            if key in kwargs and getattr(self, key) != kwargs[key]:
                reload_local = True
        for key, val in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, val)
        if reload_local:
            with self._local_lock:
                self._local_model = None
                log.info("Local Whisper config changed; will reload on next use")
        # Clear openai client cache so the new key/model picks up next call
        self._openai_client = None

    # ---- public API ----
    def ensure_loaded(self) -> None:
        """Only meaningful for local backend. OpenAI backend needs no warmup."""
        if self.backend != "local":
            return
        with self._local_lock:
            if self._local_model is None:
                self._local_model = self._load_local()

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        if audio.size == 0:
            return ""
        if sample_rate != 16000:
            raise ValueError(f"Expected 16kHz audio, got {sample_rate}Hz")
        return self._run(audio, sample_rate)

    def transcribe_partial(self, audio: np.ndarray, sample_rate: int) -> str:
        """Fast non-blocking partial transcription. Local backend only."""
        if self.backend != "local":
            return ""
        if audio.size == 0 or sample_rate != 16000:
            return ""
        if not self._inference_lock.acquire(blocking=False):
            return ""
        try:
            self.ensure_loaded()
            assert self._local_model is not None
            lang = None if self.language == "auto" else self.language
            segments, _info = self._local_model.transcribe(
                audio, language=lang, vad_filter=False,
                beam_size=1, condition_on_previous_text=False,
            )
            return " ".join(seg.text.strip() for seg in segments).strip()
        except Exception as e:  # noqa: BLE001
            log.debug("Partial transcribe failed: %s", e)
            return ""
        finally:
            self._inference_lock.release()

    def transcribe_file(self, path: str) -> str:
        """Transcribe a file from disk (both backends support this)."""
        if self.backend == "openai":
            with self._inference_lock:
                return self._openai_transcribe_file(path)
        # local backend: let faster-whisper handle decoding/resampling
        with self._inference_lock:
            self.ensure_loaded()
            return self._local_transcribe(path)

    # ---- internals ----
    def _run(self, audio: np.ndarray, sample_rate: int) -> str:
        if self.backend == "openai":
            with self._inference_lock:
                return self._openai_transcribe_array(audio, sample_rate)
        with self._inference_lock:
            self.ensure_loaded()
            return self._local_transcribe(audio)

    # -- local --
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

    def _load_local(self):
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

    def _local_transcribe(self, source) -> str:
        assert self._local_model is not None
        lang = None if self.language == "auto" else self.language
        segments, info = self._local_model.transcribe(
            source, language=lang, vad_filter=True,
            beam_size=5, condition_on_previous_text=False,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        log.info("[local] transcribed (%s, %.2fs): %s", info.language, info.duration, text[:80])
        return text

    # -- openai --
    def _resolve_openai_key(self) -> Optional[str]:
        # Env var wins (easier for shared machines / CI); config is fallback.
        env = os.environ.get("OPENAI_API_KEY", "").strip()
        return env or (self.openai_api_key or "").strip() or None

    def _get_openai_client(self):
        key = self._resolve_openai_key()
        if not key:
            raise RuntimeError(
                "OpenAI backend selected but no API key set. "
                "Add OPENAI_API_KEY to .env or paste it in Settings → Backend."
            )
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI(api_key=key)
        return self._openai_client

    def _openai_transcribe_array(self, audio: np.ndarray, sample_rate: int) -> str:
        client = self._get_openai_client()
        # Encode the float32 numpy as 16-bit PCM WAV in memory
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            pcm = np.clip(audio, -1.0, 1.0)
            pcm = (pcm * 32767.0).astype(np.int16).tobytes()
            wf.writeframes(pcm)
        buf.seek(0)
        buf.name = "audio.wav"  # openai sdk reads .name to pick content-type
        kwargs = {"model": self.openai_whisper_model, "file": buf}
        if self.language != "auto":
            kwargs["language"] = self.language
        resp = client.audio.transcriptions.create(**kwargs)
        text = getattr(resp, "text", "") or ""
        log.info("[openai] transcribed %d bytes -> %d chars", len(pcm), len(text))
        return text.strip()

    def _openai_transcribe_file(self, path: str) -> str:
        client = self._get_openai_client()
        with open(path, "rb") as f:
            kwargs = {"model": self.openai_whisper_model, "file": f}
            if self.language != "auto":
                kwargs["language"] = self.language
            resp = client.audio.transcriptions.create(**kwargs)
        return (getattr(resp, "text", "") or "").strip()
