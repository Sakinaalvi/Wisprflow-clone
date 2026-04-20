"""User configuration persisted to ~/.voxflow/config.json."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".voxflow"
CONFIG_PATH = CONFIG_DIR / "config.json"
HISTORY_PATH = CONFIG_DIR / "history.sqlite"
MODELS_DIR = CONFIG_DIR / "models"


@dataclass
class Profile:
    """A named workspace profile (custom vocab + per-profile options)."""
    name: str = "Default"
    match_apps: list[str] = field(default_factory=list)  # case-insensitive substrings of focused app name
    custom_replacements: dict[str, str] = field(default_factory=dict)
    ai_enabled_override: bool | None = None   # None = use global setting


@dataclass
class Config:
    # Transcription backend
    transcription_backend: str = "local"   # "local" (faster-whisper) | "openai" (Whisper API)

    # --- local backend (faster-whisper) ---
    model_size: str = "base"               # tiny | base | small | medium | large-v3
    device: str = "auto"                   # auto | cpu | cuda
    compute_type: str = "auto"             # auto | int8 | int8_float16 | float16 | float32

    # --- openai backend ---
    openai_whisper_model: str = "whisper-1"   # whisper-1 | gpt-4o-transcribe | gpt-4o-mini-transcribe
    openai_api_key: str = ""                  # empty = fall back to OPENAI_API_KEY env var

    # Shared
    language: str = "auto"                 # "auto" or ISO-639-1 code

    # Hotkey
    hotkey: str = "right_ctrl"
    push_to_talk: bool = True

    # Output
    output_mode: str = "type"              # type | clipboard
    type_delay_ms: int = 5

    # Audio
    sample_rate: int = 16000
    channels: int = 1
    min_record_seconds: float = 0.3

    # AI post-processing
    ai_enabled: bool = False
    ai_provider: str = "ollama"            # openai | ollama
    ollama_model: str = "llama3.2"
    ollama_url: str = "http://localhost:11434"
    voice_commands_enabled: bool = True
    custom_replacements: dict[str, str] = field(default_factory=dict)
    strip_filler_words: bool = False

    # UI
    play_sounds: bool = True
    overlay_enabled: bool = True
    show_partial_transcripts: bool = True
    partial_interval_s: float = 1.5

    # Profiles
    profiles: list[dict] = field(default_factory=list)   # list of Profile as dict
    active_profile: str = "Default"
    auto_switch_profiles: bool = False     # auto-detect focused app and switch profile

    @classmethod
    def load(cls) -> "Config":
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_PATH.exists():
            cfg = cls()
            cfg.save()
            return cfg
        try:
            data: dict[str, Any] = json.loads(CONFIG_PATH.read_text())
            defaults = asdict(cls())
            defaults.update({k: v for k, v in data.items() if k in defaults})
            return cls(**defaults)
        except (json.JSONDecodeError, TypeError) as e:
            log.warning("Bad config file, resetting: %s", e)
            cfg = cls()
            cfg.save()
            return cfg

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2))

    # ---- profile helpers ----
    def get_profile(self, name: str) -> Profile | None:
        for p in self.profiles:
            if p.get("name") == name:
                return Profile(**{**asdict(Profile()), **p})
        return None

    def get_active_profile(self) -> Profile | None:
        return self.get_profile(self.active_profile)

    def effective_replacements(self, active: Profile | None = None) -> dict[str, str]:
        """Global replacements merged with active profile's (profile wins)."""
        merged = dict(self.custom_replacements)
        prof = active if active is not None else self.get_active_profile()
        if prof is not None:
            merged.update(prof.custom_replacements)
        return merged

    def effective_ai_enabled(self, active: Profile | None = None) -> bool:
        prof = active if active is not None else self.get_active_profile()
        if prof is not None and prof.ai_enabled_override is not None:
            return prof.ai_enabled_override
        return self.ai_enabled
