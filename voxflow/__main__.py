"""Entry point: `python -m voxflow` (tray app) or `python -m voxflow transcribe <file>` (CLI)."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv


def _run_tray() -> None:
    from voxflow.app import VoxFlowApp
    app = VoxFlowApp()
    try:
        app.run()
    except KeyboardInterrupt:
        app.shutdown()


def _run_transcribe(args: argparse.Namespace) -> int:
    from voxflow.config import Config
    from voxflow.post_processor import PostProcessor
    from voxflow.transcriber import Transcriber

    cfg = Config.load()
    model_size = args.model or cfg.model_size
    language = args.language or cfg.language
    device = args.device or cfg.device

    path = Path(args.file).expanduser().resolve()
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    print(f"Loading Whisper '{model_size}' on {device}...", file=sys.stderr)
    tr = Transcriber(
        model_size=model_size,
        device=device,
        compute_type=cfg.compute_type,
        language=language,
    )
    raw = tr.transcribe_file(str(path))
    text = raw
    if args.post:
        pp = PostProcessor(
            voice_commands_enabled=cfg.voice_commands_enabled,
            custom_replacements=cfg.custom_replacements,
            strip_filler_words=cfg.strip_filler_words,
            ai_enabled=args.ai,
            ai_provider=args.ai_provider or cfg.ai_provider,
            ollama_model=cfg.ollama_model,
            ollama_url=cfg.ollama_url,
        )
        text = pp.process(raw)

    print(text)
    return 0


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        prog="voxflow",
        description="VoxFlow — local voice dictation. No subcommand = launch tray app.",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_tx = sub.add_parser("transcribe", help="Transcribe an audio file from disk.")
    p_tx.add_argument("file", help="Path to .wav / .mp3 / .flac / .m4a audio file.")
    p_tx.add_argument("--model", help="Override model size (tiny/base/small/medium/large-v3)")
    p_tx.add_argument("--language", help="Language code or 'auto'")
    p_tx.add_argument("--device", choices=["auto", "cpu", "cuda"], help="Compute device")
    p_tx.add_argument("--post", action="store_true",
                      help="Apply voice commands + custom replacements post-processing")
    p_tx.add_argument("--ai", action="store_true",
                      help="Also run AI cleanup (needs --post; uses configured provider)")
    p_tx.add_argument("--ai-provider", choices=["openai", "ollama"],
                      help="Override AI provider for this run")

    args = parser.parse_args()

    if args.cmd == "transcribe":
        sys.exit(_run_transcribe(args))
    else:
        _run_tray()


if __name__ == "__main__":
    main()
