# VoxFlow

**An enhanced, local-first voice dictation app. A free, unlimited alternative to WhisperFlow / Wispr Flow.**

VoxFlow runs [OpenAI Whisper](https://github.com/openai/whisper) entirely on your own machine using [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper). Press a hotkey, speak, and your words are typed into whatever app you're using — no cloud, no rate limits, no subscription.

---

## Features

- **100% local transcription** — runs fully offline on CPU or GPU (CUDA).
- **Hold-to-talk global hotkey** — configurable (default: `Right Ctrl`).
- **Auto-type at cursor** — transcribed text is injected into the focused app, just like WhisperFlow.
- **Clipboard mode** — alternative output if auto-typing is blocked.
- **AI post-processing** *(optional)* — clean up filler words, add punctuation, fix grammar with an OpenAI API key.
- **Custom vocabulary** — teach VoxFlow your jargon, names, and replacements (e.g. `"my email" → "me@example.com"`).
- **Voice commands** — say "new line", "new paragraph", "period", "comma", "question mark", etc.
- **History with search** — all transcriptions saved locally in SQLite. Export to TXT / Markdown.
- **Multi-language** — 99 Whisper-supported languages.
- **Multiple model sizes** — `tiny` (fastest) → `large-v3` (most accurate). Switch any time.
- **Tray icon + settings GUI** — runs quietly in the background.
- **Cross-platform** — Windows, macOS, Linux.

---

## Why VoxFlow over WhisperFlow / Wispr Flow?

| | VoxFlow | WhisperFlow |
|---|---|---|
| Cost | Free, open source | Paid subscription |
| Rate limits | None | Yes (free tier) |
| Privacy | All local, offline | Cloud |
| Accuracy | `large-v3` = SOTA | Good |
| Custom vocabulary | Yes | Limited |
| GPU acceleration | Yes (CUDA) | N/A |
| Customizable | Fully (open source) | No |

---

## Installation

### Prerequisites

- **Python 3.10+**
- **ffmpeg** (for audio)
  - macOS: `brew install ffmpeg portaudio`
  - Ubuntu/Debian: `sudo apt install ffmpeg portaudio19-dev python3-dev`
  - Windows: [download ffmpeg](https://www.gyan.dev/ffmpeg/builds/) and add to PATH
- **(Optional) NVIDIA GPU + CUDA 12** for much faster transcription

### Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/voxflow.git
cd voxflow

# Create a virtual env (recommended)
python -m venv .venv
source .venv/bin/activate     # On Windows: .venv\Scripts\activate

# Install
pip install -r requirements.txt
```

### First run

```bash
python -m voxflow
```

On first launch the Whisper model will download (~150 MB for `base`, ~3 GB for `large-v3`). Grab coffee.

A tray icon appears in your system tray. Right-click it for settings.

**Default hotkey:** hold `Right Ctrl`, speak, release. Transcribed text is typed at the cursor.

---

## Platform-specific permissions

### macOS
You must grant:
1. **Accessibility** (for global hotkey + auto-typing) — System Settings → Privacy & Security → Accessibility → add Terminal / Python.
2. **Microphone** — will be prompted on first record.
3. **Input Monitoring** — System Settings → Privacy & Security → Input Monitoring.

### Linux (Wayland)
`pynput` has limited Wayland support. For best results run under X11, or use clipboard mode (enabled in settings).

### Windows
No special setup required. If hotkeys fail to register globally, run your terminal as Administrator.

---

## Configuration

Settings are stored in `~/.voxflow/config.json` and editable from the GUI:

- **Model size** — `tiny`, `base`, `small`, `medium`, `large-v3`
- **Language** — `auto` or any ISO code (`en`, `fr`, `es`, `de`, `ja`, ...)
- **Compute device** — `auto`, `cpu`, `cuda`
- **Hotkey** — any key or combo (`right_ctrl`, `f9`, `ctrl+alt+space`, ...)
- **Output mode** — `type` (auto-type) or `clipboard` (copy only)
- **AI post-processing** — off / on (needs `OPENAI_API_KEY` in `.env`)
- **Custom replacements** — JSON dictionary of `"phrase": "replacement"`
- **Voice commands** — toggle built-in commands

### AI post-processing (optional)

VoxFlow supports two AI providers for cleanup:

#### Option A — Ollama (100% local, recommended)

Runs entirely on your PC. No API key, no data leaves your machine.

```bash
# Install Ollama from https://ollama.com (one-time)
ollama pull llama3.2     # or llama3.1, qwen2.5, mistral, ...
ollama serve             # starts the local server on :11434
```

Then in VoxFlow settings → **AI & Vocabulary** tab:
- Enable "AI post-processing"
- Provider: **ollama**
- Ollama model: **llama3.2** (or whatever you pulled)

#### Option B — OpenAI (cloud)

Create `.env` in the project root:

```env
OPENAI_API_KEY=sk-...
AI_MODEL=gpt-4o-mini
```

In settings, set Provider: **openai**.

Either way, VoxFlow passes your raw transcript through the model with a prompt to fix punctuation, remove filler words, and format lists/paragraphs.

---

## CLI mode (quick smoke test without mic/hotkey)

Want to verify transcription quality before wiring up mic & hotkeys? Transcribe an audio file directly:

```bash
# basic
python -m voxflow transcribe path/to/audio.wav

# with post-processing (voice commands + custom vocabulary)
python -m voxflow transcribe audio.mp3 --post

# with AI cleanup (uses the configured provider, e.g. ollama)
python -m voxflow transcribe audio.mp3 --post --ai

# override model for a one-off run
python -m voxflow transcribe audio.wav --model large-v3 --language en --device cuda
```

Accepts any format `ffmpeg` supports (`.wav`, `.mp3`, `.flac`, `.m4a`, `.ogg`, ...).

---

## Usage tips

- **Short phrase?** Hold hotkey, say it, release. Instant.
- **Long dictation?** Hold hotkey the whole time. VoxFlow buffers silently.
- **Mis-recognition?** Open history, edit, or add to custom vocabulary.
- **GPU is much faster.** On a 3060 the `large-v3` model transcribes real-time. On CPU use `base` or `small`.

---

## Voice commands (built-in)

| You say | Output |
|---|---|
| "new line" | `\n` |
| "new paragraph" | `\n\n` |
| "period" / "full stop" | `.` |
| "comma" | `,` |
| "question mark" | `?` |
| "exclamation mark" | `!` |
| "colon" | `:` |
| "semicolon" | `;` |
| "open quote" / "close quote" | `"` |
| "open paren" / "close paren" | `(` / `)` |

---

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

Project layout:

```
voxflow/
├── __main__.py          # entry point
├── app.py               # main controller + tray
├── recorder.py          # microphone capture
├── transcriber.py       # faster-whisper wrapper
├── post_processor.py    # AI cleanup + voice commands
├── typer.py             # auto-type / clipboard
├── hotkeys.py           # global hotkey manager
├── config.py            # settings persistence
├── history.py           # SQLite history
└── ui/
    ├── settings_window.py
    └── history_window.py
```

---

## Roadmap

- [ ] Real-time streaming transcription (live partial results)
- [ ] Per-app profiles (e.g. different vocab for Slack vs. VS Code)
- [ ] Plugin system for custom post-processors
- [x] Local LLM post-processing (Ollama) ✅
- [ ] Auto-start on login installer
- [ ] Packaged binaries (PyInstaller) for Win/Mac/Linux

PRs welcome.

---

## License

MIT © 2026
