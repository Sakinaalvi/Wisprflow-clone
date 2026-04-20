# VoxFlow

**An enhanced, local-first voice dictation app. A free, unlimited alternative to WhisperFlow / Wispr Flow.**

VoxFlow runs [OpenAI Whisper](https://github.com/openai/whisper) entirely on your own machine using [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper). Press a hotkey, speak, and your words are typed into whatever app you're using — no cloud, no rate limits, no subscription.

---

## Features

## Features

- **Two transcription backends** — switch any time from Settings or tray:
  - **Local** (`faster-whisper`) — runs Whisper on your CPU/GPU. Free, offline, no rate limits.
  - **OpenAI API** — uses OpenAI's Whisper / `gpt-4o-transcribe` models. Fastest, most accurate, uses your API key.
- **Hold-to-talk global hotkey** — configurable (default: `Right Ctrl`).
- **Live overlay** — always-on-top waveform + partial transcript while you speak.
- **Auto-type at cursor** — transcribed text is injected into the focused app, just like WhisperFlow.
- **Clipboard mode** — alternative output if auto-typing is blocked.
- **AI post-processing** *(optional)* — clean up filler words, add punctuation, fix grammar with either local **Ollama** (no API key, fully offline) or **OpenAI**.
- **Per-app profiles** — different custom vocabularies that auto-switch based on the focused app (e.g. "Code" profile for VS Code, "Slack" profile for Slack).
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

## Transcription backends

VoxFlow ships two backends and you can flip between them at any time via **Settings → Backend** or the tray **Backend** submenu.

### Local (default)
`faster-whisper` runs Whisper entirely on your machine. CUDA GPU auto-detected.
- **Pros:** free, offline, no rate limits, private.
- **Cons:** large models need RAM / VRAM; CPU-only is slower.

### OpenAI API
Uses OpenAI's hosted Whisper / `gpt-4o-transcribe` endpoints.
- **Pros:** fastest end-to-end latency, state-of-the-art accuracy without needing a GPU.
- **Cons:** needs internet + an API key (you pay per minute of audio).

**How to supply your key:**

Option 1 — paste into the app: **Settings → Backend → API key**. Stored in `~/.voxflow/config.json` (plain text; don't use on shared machines).

Option 2 — environment variable: put `OPENAI_API_KEY=sk-...` in `.env` at the project root. The env var wins over the config value.

Available OpenAI models:
- `whisper-1` — the classic Whisper endpoint, balanced cost/accuracy.
- `gpt-4o-transcribe` — best accuracy.
- `gpt-4o-mini-transcribe` — cheapest, still very good.

---

## AI post-processing (optional)

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

Transcribe an audio file directly, no tray/hotkey needed:

```bash
# local backend (default)
python -m voxflow transcribe path/to/audio.wav

# use OpenAI backend for this one run
python -m voxflow transcribe audio.mp3 --backend openai

# with post-processing + AI cleanup
python -m voxflow transcribe audio.mp3 --post --ai

# override everything
python -m voxflow transcribe audio.wav --backend local --model large-v3 --language en --device cuda
```

Accepts any format `ffmpeg` supports (`.wav`, `.mp3`, `.flac`, `.m4a`, `.ogg`, ...).

---

## Per-app profiles

You can define multiple profiles with different custom vocabularies, and VoxFlow will switch between them automatically based on the focused app.

**Example:** "Code" profile expands `"api"` → `"API"` when VS Code is focused; "Slack" profile uses AI cleanup; "Default" is used everywhere else.

In **Settings → Profiles** tab, define a JSON list like:
```json
[
  {"name": "Default", "match_apps": [], "custom_replacements": {}},
  {"name": "Code", "match_apps": ["code", "vscode", "pycharm"],
   "custom_replacements": {"gpt": "GPT", "api": "API", "ui": "UI"}},
  {"name": "Slack", "match_apps": ["slack"],
   "custom_replacements": {}, "ai_enabled_override": true}
]
```
Then check **"Auto-switch profile based on focused app"**.

Focused-app detection is best-effort per OS:
- **Windows**: uses `user32`/`psapi` (built-in).
- **macOS**: uses `osascript` (built-in) — requires Accessibility permission.
- **Linux**: requires `xdotool` installed (`sudo apt install xdotool`).

You can also switch manually from the tray **Profile** submenu.

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

## Downloads (pre-built binaries)

Don't want to install Python? Every tagged release (`v*`) auto-builds standalone binaries for **Windows, macOS, and Linux** via GitHub Actions.

Check the [Releases](../../releases) page for `.zip` (Windows) / `.tar.gz` (macOS, Linux) archives. Unpack, run `voxflow`, done.

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

- [x] Live overlay with waveform + partial transcripts ✅
- [x] Local LLM post-processing (Ollama) ✅
- [x] CLI mode (`voxflow transcribe <file>`) ✅
- [x] OpenAI Whisper API backend option ✅
- [x] Per-app vocabulary profiles ✅
- [x] Packaged binaries via PyInstaller + GitHub Actions ✅
- [ ] Real-time streaming partial transcripts (WebSocket-style continuous feed)
- [ ] Plugin system for custom post-processors
- [ ] Auto-start on login installer

PRs welcome.

---

## License

MIT © 2026
