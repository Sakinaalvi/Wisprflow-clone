"""Text post-processing: voice commands, custom replacements, filler strip, optional AI cleanup.

AI providers:
  - "openai": uses OPENAI_API_KEY from env (cloud).
  - "ollama": uses local Ollama server (http://localhost:11434 by default). 100% local, no key.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)

VOICE_COMMANDS: dict[str, str] = {
    r"\bnew paragraph\b": "\n\n",
    r"\bnew line\b": "\n",
    r"\bfull stop\b": ".",
    r"\bperiod\b": ".",
    r"\bcomma\b": ",",
    r"\bquestion mark\b": "?",
    r"\bexclamation mark\b": "!",
    r"\bcolon\b": ":",
    r"\bsemicolon\b": ";",
    r"\bopen quote\b": '"',
    r"\bclose quote\b": '"',
    r"\bopen paren(thesis)?\b": "(",
    r"\bclose paren(thesis)?\b": ")",
    r"\bdash\b": "-",
    r"\bhyphen\b": "-",
}

FILLERS = [
    r"\bum+\b",
    r"\buh+\b",
    r"\ber+\b",
    r"\bhmm+\b",
    r"\blike\b(?=,? like\b)",
    r"\byou know\b",
    r"\bbasically\b",
]

AI_SYSTEM_PROMPT = (
    "You are a dictation cleanup assistant. Clean up the user's dictated text. "
    "Add correct punctuation and capitalization. Fix obvious grammar and remove "
    "filler words (um, uh, like, you know). Preserve meaning and intent exactly. "
    "Do NOT add new information. Do NOT answer questions in the text. "
    "Return ONLY the cleaned text — no preamble, no explanation, no quotes."
)


class PostProcessor:
    def __init__(
        self,
        voice_commands_enabled: bool,
        custom_replacements: dict[str, str],
        strip_filler_words: bool,
        ai_enabled: bool,
        ai_provider: str = "ollama",
        ollama_model: str = "llama3.2",
        ollama_url: str = "http://localhost:11434",
    ) -> None:
        self.voice_commands_enabled = voice_commands_enabled
        self.custom_replacements = custom_replacements
        self.strip_filler_words = strip_filler_words
        self.ai_enabled = ai_enabled
        self.ai_provider = ai_provider
        self.ollama_model = ollama_model
        self.ollama_url = ollama_url.rstrip("/")
        self._openai_client = None

    def update(
        self,
        voice_commands_enabled: bool,
        custom_replacements: dict[str, str],
        strip_filler_words: bool,
        ai_enabled: bool,
        ai_provider: str = "ollama",
        ollama_model: str = "llama3.2",
        ollama_url: str = "http://localhost:11434",
    ) -> None:
        self.voice_commands_enabled = voice_commands_enabled
        self.custom_replacements = custom_replacements
        self.strip_filler_words = strip_filler_words
        self.ai_enabled = ai_enabled
        self.ai_provider = ai_provider
        self.ollama_model = ollama_model
        self.ollama_url = ollama_url.rstrip("/")

    def process(self, text: str) -> str:
        if not text:
            return ""

        if self.ai_enabled:
            cleaned = self._ai_cleanup(text)
            if cleaned:
                text = cleaned
        else:
            if self.strip_filler_words:
                text = self._strip_fillers(text)

        if self.voice_commands_enabled:
            text = self._apply_voice_commands(text)

        text = self._apply_custom_replacements(text)
        text = self._tidy_whitespace(text)
        return text

    # ----- local rules -----
    @staticmethod
    def _strip_fillers(text: str) -> str:
        for pat in FILLERS:
            text = re.sub(pat, "", text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def _apply_voice_commands(text: str) -> str:
        for pat, rep in VOICE_COMMANDS.items():
            text = re.sub(pat, rep, text, flags=re.IGNORECASE)
        text = re.sub(r"\s+([.,?!;:])", r"\1", text)
        return text

    def _apply_custom_replacements(self, text: str) -> str:
        if not self.custom_replacements:
            return text
        for phrase, rep in self.custom_replacements.items():
            if not phrase:
                continue
            text = re.sub(r"\b" + re.escape(phrase) + r"\b", rep, text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def _tidy_whitespace(text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        return text.strip()

    # ----- AI providers -----
    def _ai_cleanup(self, text: str) -> Optional[str]:
        if self.ai_provider == "ollama":
            return self._ollama_cleanup(text)
        if self.ai_provider == "openai":
            return self._openai_cleanup(text)
        log.warning("Unknown ai_provider: %s", self.ai_provider)
        return None

    def _openai_cleanup(self, text: str) -> Optional[str]:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            log.warning("AI post-processing enabled but OPENAI_API_KEY is missing.")
            return None
        try:
            if self._openai_client is None:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=api_key)
            model = os.environ.get("AI_MODEL", "gpt-4o-mini")
            resp = self._openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": AI_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0.2,
                max_tokens=1500,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:  # noqa: BLE001
            log.error("OpenAI cleanup failed: %s", e)
            return None

    def _ollama_cleanup(self, text: str) -> Optional[str]:
        """Call local Ollama /api/chat with the cleanup prompt. Stdlib only."""
        url = f"{self.ollama_url}/api/chat"
        payload = {
            "model": self.ollama_model,
            "stream": False,
            "options": {"temperature": 0.2},
            "messages": [
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8")
            obj = json.loads(body)
            content = (obj.get("message") or {}).get("content", "").strip()
            return content or None
        except urllib.error.URLError as e:
            log.error(
                "Ollama not reachable at %s (%s). Is it running? `ollama serve`",
                self.ollama_url, e,
            )
            return None
        except (json.JSONDecodeError, KeyError) as e:
            log.error("Ollama response parse error: %s", e)
            return None
