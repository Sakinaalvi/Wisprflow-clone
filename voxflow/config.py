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
class Config:
    # Model
    model_size: str = "base"         # tiny | base | small | medium | large-v3
    language: str = "auto"           # "auto" or ISO-639-1 code
    device: str = "auto"             # auto | cpu | cuda
    compute_type: str = "auto"       # auto | int8 | int8_float16 | float16 | float32

    # Hotkey
    hotkey: str = "right_ctrl"       # single key or combo, see hotkeys.py
    push_to_talk: bool = True        # hold-to-talk when True; toggle when False

    # Output
    output_mode: str = "type"        # type | clipboard
    type_delay_ms: int = 5           # per-char delay for auto-typing

    # Audio
    sample_rate: int = 16000
    channels: int = 1
    min_record_seconds: float = 0.3  # ignore taps shorter than this

    # Post-processing
    ai_enabled: bool = False
    ai_provider: str = "ollama"      # openai | ollama
    ollama_model: str = "llama3.2"
    ollama_url: str = "http://localhost:11434"
    voice_commands_enabled: bool = True
    custom_replacements: dict[str, str] = field(default_factory=dict)
    strip_filler_words: bool = False  # simple local cleanup

    # UI
    play_sounds: bool = True

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
