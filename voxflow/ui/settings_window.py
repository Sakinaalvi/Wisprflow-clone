"""Settings window (tkinter). Edits config and triggers on_save callback."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from voxflow.config import Config

MODEL_SIZES = ["tiny", "base", "small", "medium", "large-v3"]
LANGUAGES = ["auto", "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru",
             "zh", "ja", "ko", "ar", "hi", "tr", "sv", "no", "da", "fi"]
DEVICES = ["auto", "cpu", "cuda"]
COMPUTE_TYPES = ["auto", "int8", "int8_float16", "float16", "float32"]
OUTPUT_MODES = ["type", "clipboard"]
BACKENDS = ["local", "openai"]
OPENAI_MODELS = ["whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe"]


class SettingsWindow:
    def __init__(self, config: Config, on_save: Callable[[], None]) -> None:
        self.config = config
        self.on_save = on_save
        self.root: tk.Tk | None = None

    def show(self) -> None:
        self.root = tk.Tk()
        self.root.title("VoxFlow — Settings")
        self.root.geometry("600x720")

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=12, pady=12)

        nb.add(self._build_backend_tab(nb), text="Backend")
        nb.add(self._build_transcription_tab(nb), text="Transcription")
        nb.add(self._build_hotkey_tab(nb), text="Hotkey")
        nb.add(self._build_output_tab(nb), text="Output")
        nb.add(self._build_ai_tab(nb), text="AI & Vocabulary")
        nb.add(self._build_profiles_tab(nb), text="Profiles")

        btns = ttk.Frame(self.root)
        btns.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(btns, text="Cancel", command=self.root.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=self._save).pack(side="right", padx=6)

        self.root.mainloop()

    # ----- Backend tab -----
    def _build_backend_tab(self, parent) -> ttk.Frame:
        f = ttk.Frame(parent, padding=16)
        self.var_backend = tk.StringVar(value=self.config.transcription_backend)
        self.var_oa_model = tk.StringVar(value=self.config.openai_whisper_model)
        self.var_oa_key = tk.StringVar(value=self.config.openai_api_key)

        ttk.Label(
            f, text="Choose where transcription runs.",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(f, text="Backend").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(
            f, textvariable=self.var_backend, values=BACKENDS,
            state="readonly", width=20,
        ).grid(row=1, column=1, sticky="w")
        ttk.Label(
            f,
            text=(
                "local  = runs Whisper on your PC (faster-whisper). No rate limits, offline, free.\n"
                "openai = uses OpenAI's Whisper API. Fastest, highest accuracy, needs API key + internet."
            ),
            foreground="#666", wraplength=520, justify="left",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 14))

        ttk.Separator(f, orient="horizontal").grid(
            row=3, column=0, columnspan=2, sticky="we", pady=8
        )
        ttk.Label(
            f, text="OpenAI settings (used when backend = openai)",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(f, text="Model").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Combobox(
            f, textvariable=self.var_oa_model, values=OPENAI_MODELS,
            state="readonly", width=30,
        ).grid(row=5, column=1, sticky="w")
        ttk.Label(
            f,
            text="whisper-1 = classic. gpt-4o-transcribe = best accuracy. gpt-4o-mini-transcribe = cheaper.",
            foreground="#666", wraplength=520, justify="left",
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(f, text="API key").grid(row=7, column=0, sticky="w", pady=4)
        self.entry_oa_key = ttk.Entry(f, textvariable=self.var_oa_key, width=48, show="*")
        self.entry_oa_key.grid(row=7, column=1, sticky="w")

        self.var_show_key = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            f, text="Show key", variable=self.var_show_key,
            command=self._toggle_show_key,
        ).grid(row=8, column=1, sticky="w")

        ttk.Label(
            f,
            text=(
                "Paste your OpenAI key here (sk-...). Leave blank to fall back to the "
                "OPENAI_API_KEY env var / .env file. Stored locally in plain text at "
                "~/.voxflow/config.json — don't use on shared machines."
            ),
            foreground="#666", wraplength=520, justify="left",
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(4, 0))
        return f

    def _toggle_show_key(self) -> None:
        self.entry_oa_key.config(show="" if self.var_show_key.get() else "*")

    # ----- Transcription tab (local-backend settings) -----
    def _build_transcription_tab(self, parent) -> ttk.Frame:
        f = ttk.Frame(parent, padding=16)
        self.var_model = tk.StringVar(value=self.config.model_size)
        self.var_lang = tk.StringVar(value=self.config.language)
        self.var_device = tk.StringVar(value=self.config.device)
        self.var_compute = tk.StringVar(value=self.config.compute_type)

        ttk.Label(
            f, text="Local backend settings (faster-whisper). Language applies to both backends.",
            foreground="#666", wraplength=520, justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self._combo(f, "Model size", MODEL_SIZES, self.var_model, 1,
                    hint="tiny = fastest, large-v3 = most accurate")
        self._combo(f, "Language", LANGUAGES, self.var_lang, 2,
                    hint="auto = detect per utterance")
        self._combo(f, "Device", DEVICES, self.var_device, 3,
                    hint="cuda requires NVIDIA GPU + CUDA 12")
        self._combo(f, "Compute type", COMPUTE_TYPES, self.var_compute, 4,
                    hint="auto picks best for your device")
        return f

    # ----- Hotkey tab -----
    def _build_hotkey_tab(self, parent) -> ttk.Frame:
        f = ttk.Frame(parent, padding=16)
        self.var_hotkey = tk.StringVar(value=self.config.hotkey)
        self.var_ptt = tk.BooleanVar(value=self.config.push_to_talk)

        ttk.Label(f, text="Hotkey").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.var_hotkey, width=28).grid(row=0, column=1, sticky="w")
        ttk.Label(
            f, text="Examples: right_ctrl, f9, caps_lock, ctrl+alt+space", foreground="#666",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 12))

        ttk.Checkbutton(
            f, text="Push-to-talk (hold to record). Uncheck for tap-to-toggle.",
            variable=self.var_ptt,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Label(
            f, text="Note: combos (ctrl+alt+...) always use toggle mode.", foreground="#666",
        ).grid(row=3, column=0, columnspan=2, sticky="w")
        return f

    # ----- Output tab -----
    def _build_output_tab(self, parent) -> ttk.Frame:
        f = ttk.Frame(parent, padding=16)
        self.var_out = tk.StringVar(value=self.config.output_mode)
        self.var_delay = tk.IntVar(value=self.config.type_delay_ms)
        self.var_sounds = tk.BooleanVar(value=self.config.play_sounds)

        self._combo(f, "Output mode", OUTPUT_MODES, self.var_out, 0,
                    hint="type = auto-type at cursor; clipboard = copy only")

        ttk.Label(f, text="Type delay (ms)").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Spinbox(f, from_=0, to=100, textvariable=self.var_delay, width=8).grid(
            row=2, column=1, sticky="w"
        )
        ttk.Label(f, text="Increase if characters get dropped.", foreground="#666").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(2, 12)
        )

        ttk.Checkbutton(
            f, text="Play subtle sounds on record/stop", variable=self.var_sounds,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=4)

        self.var_overlay = tk.BooleanVar(value=self.config.overlay_enabled)
        self.var_partials = tk.BooleanVar(value=self.config.show_partial_transcripts)

        ttk.Separator(f, orient="horizontal").grid(
            row=5, column=0, columnspan=2, sticky="we", pady=12
        )
        ttk.Label(f, text="Live overlay", font=("TkDefaultFont", 10, "bold")).grid(
            row=6, column=0, columnspan=2, sticky="w"
        )
        ttk.Checkbutton(
            f, text="Show live waveform + status overlay while recording",
            variable=self.var_overlay,
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(
            f, text="Show partial transcripts in overlay (updates ~1.5s, local backend only)",
            variable=self.var_partials,
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=4)
        return f

    # ----- AI tab -----
    def _build_ai_tab(self, parent) -> ttk.Frame:
        f = ttk.Frame(parent, padding=16)
        self.var_ai = tk.BooleanVar(value=self.config.ai_enabled)
        self.var_provider = tk.StringVar(value=self.config.ai_provider)
        self.var_ollama_model = tk.StringVar(value=self.config.ollama_model)
        self.var_ollama_url = tk.StringVar(value=self.config.ollama_url)
        self.var_vc = tk.BooleanVar(value=self.config.voice_commands_enabled)
        self.var_fillers = tk.BooleanVar(value=self.config.strip_filler_words)

        ttk.Checkbutton(
            f, text="Enable AI post-processing", variable=self.var_ai,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)

        ttk.Label(f, text="Provider").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(
            f, textvariable=self.var_provider, values=["ollama", "openai"],
            state="readonly", width=20,
        ).grid(row=1, column=1, sticky="w")
        ttk.Label(
            f,
            text="ollama = 100% local. openai = cloud, uses the API key in Backend tab.",
            foreground="#666", wraplength=520, justify="left",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(f, text="Ollama model").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.var_ollama_model, width=24).grid(
            row=3, column=1, sticky="w"
        )
        ttk.Label(
            f, text="e.g. llama3.2, llama3.1, qwen2.5, mistral", foreground="#666",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(f, text="Ollama URL").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.var_ollama_url, width=30).grid(
            row=5, column=1, sticky="w"
        )

        ttk.Checkbutton(
            f, text='Enable voice commands ("new line", "period", ...)',
            variable=self.var_vc,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(12, 4))

        ttk.Checkbutton(
            f, text="Strip common filler words locally (um, uh, like, you know)",
            variable=self.var_fillers,
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=4)

        ttk.Label(f, text="Global custom replacements (JSON)").grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(16, 4)
        )
        self.txt_replacements = tk.Text(f, height=8, width=64)
        self.txt_replacements.grid(row=9, column=0, columnspan=2, sticky="we")
        self.txt_replacements.insert(
            "1.0", json.dumps(self.config.custom_replacements, indent=2) or "{}"
        )

        ttk.Label(
            f,
            text='Example: {"my email": "me@example.com", "gpg": "GPG"}',
            foreground="#666",
        ).grid(row=10, column=0, columnspan=2, sticky="w", pady=(4, 0))
        return f

    # ----- Profiles tab -----
    def _build_profiles_tab(self, parent) -> ttk.Frame:
        f = ttk.Frame(parent, padding=16)
        self.var_auto_switch = tk.BooleanVar(value=self.config.auto_switch_profiles)

        ttk.Label(
            f,
            text=(
                "Profiles let you use different vocabularies for different apps. "
                "Each profile has its own custom replacements. Enable auto-switch to "
                "pick the profile whose 'match_apps' matches the currently focused app."
            ),
            foreground="#666", wraplength=540, justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Checkbutton(
            f, text="Auto-switch profile based on focused app (best-effort per-OS detection)",
            variable=self.var_auto_switch,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(f, text="Profiles (JSON list)").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(4, 4)
        )
        self.txt_profiles = tk.Text(f, height=22, width=72)
        self.txt_profiles.grid(row=3, column=0, columnspan=2, sticky="we")
        self.txt_profiles.insert("1.0", json.dumps(self.config.profiles, indent=2) or "[]")

        ttk.Label(
            f,
            text=(
                'Example:\n'
                '[\n'
                '  {"name": "Default", "match_apps": [], "custom_replacements": {}},\n'
                '  {"name": "Code", "match_apps": ["code", "vscode"],\n'
                '   "custom_replacements": {"gpt": "GPT", "api": "API"}},\n'
                '  {"name": "Slack", "match_apps": ["slack"],\n'
                '   "custom_replacements": {}, "ai_enabled_override": true}\n'
                ']'
            ),
            foreground="#666", font=("TkFixedFont", 9), justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))
        return f

    # ----- helpers -----
    @staticmethod
    def _combo(parent, label: str, values, var, row: int, hint: str = "") -> None:
        ttk.Label(parent, text=label).grid(row=row * 2, column=0, sticky="w", pady=4)
        ttk.Combobox(parent, textvariable=var, values=values, state="readonly", width=25).grid(
            row=row * 2, column=1, sticky="w"
        )
        if hint:
            ttk.Label(parent, text=hint, foreground="#666").grid(
                row=row * 2 + 1, column=0, columnspan=2, sticky="w", pady=(0, 8)
            )

    def _save(self) -> None:
        try:
            replacements = json.loads(self.txt_replacements.get("1.0", "end").strip() or "{}")
            if not isinstance(replacements, dict):
                raise ValueError("Replacements must be a JSON object.")
            replacements = {str(k): str(v) for k, v in replacements.items()}
        except (json.JSONDecodeError, ValueError) as e:
            messagebox.showerror("Invalid replacements", f"JSON error: {e}")
            return

        try:
            profiles = json.loads(self.txt_profiles.get("1.0", "end").strip() or "[]")
            if not isinstance(profiles, list):
                raise ValueError("Profiles must be a JSON list.")
            for p in profiles:
                if not isinstance(p, dict) or "name" not in p:
                    raise ValueError("Each profile must be an object with a 'name'.")
        except (json.JSONDecodeError, ValueError) as e:
            messagebox.showerror("Invalid profiles", f"JSON error: {e}")
            return

        # Transcription backend
        self.config.transcription_backend = self.var_backend.get()
        self.config.openai_whisper_model = self.var_oa_model.get()
        self.config.openai_api_key = self.var_oa_key.get().strip()

        # Model / lang
        self.config.model_size = self.var_model.get()
        self.config.language = self.var_lang.get()
        self.config.device = self.var_device.get()
        self.config.compute_type = self.var_compute.get()

        # Hotkey
        self.config.hotkey = self.var_hotkey.get().strip() or "right_ctrl"
        self.config.push_to_talk = bool(self.var_ptt.get())

        # Output
        self.config.output_mode = self.var_out.get()
        self.config.type_delay_ms = int(self.var_delay.get())
        self.config.play_sounds = bool(self.var_sounds.get())
        self.config.overlay_enabled = bool(self.var_overlay.get())
        self.config.show_partial_transcripts = bool(self.var_partials.get())

        # AI
        self.config.ai_enabled = bool(self.var_ai.get())
        self.config.ai_provider = self.var_provider.get()
        self.config.ollama_model = self.var_ollama_model.get().strip() or "llama3.2"
        self.config.ollama_url = self.var_ollama_url.get().strip() or "http://localhost:11434"
        self.config.voice_commands_enabled = bool(self.var_vc.get())
        self.config.strip_filler_words = bool(self.var_fillers.get())
        self.config.custom_replacements = replacements

        # Profiles
        self.config.auto_switch_profiles = bool(self.var_auto_switch.get())
        self.config.profiles = profiles

        self.on_save()
        if self.root is not None:
            self.root.destroy()
