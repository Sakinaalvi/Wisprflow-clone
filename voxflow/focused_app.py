"""Best-effort cross-platform focused-window detection for per-app profile auto-switch.

Returns a short human-readable app name (e.g. "Code", "Slack", "firefox") or "" if unknown.
Each platform uses stdlib-only calls where possible:
  - Windows: ctypes + user32/psapi
  - macOS:   osascript (built-in)
  - Linux:   xdotool (must be installed by the user)
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def get_focused_app_name() -> str:
    try:
        if sys.platform == "win32":
            return _win()
        if sys.platform == "darwin":
            return _mac()
        return _linux()
    except Exception as e:  # noqa: BLE001
        log.debug("focused app detect failed: %s", e)
        return ""


def _win() -> str:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        psapi.GetModuleFileNameExW(h, None, buf, 1024)
        return Path(buf.value).stem if buf.value else ""
    finally:
        kernel32.CloseHandle(h)


def _mac() -> str:
    out = subprocess.run(
        ["osascript", "-e",
         'tell application "System Events" to get name of first application process '
         'whose frontmost is true'],
        capture_output=True, text=True, timeout=1.5,
    )
    return (out.stdout or "").strip()


def _linux() -> str:
    # xdotool getactivewindow getwindowclassname gives short names like "code", "firefox"
    out = subprocess.run(
        ["xdotool", "getactivewindow", "getwindowclassname"],
        capture_output=True, text=True, timeout=1.5,
    )
    name = (out.stdout or "").strip()
    return name
