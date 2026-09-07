"""Which theme the OS is asking for — light or dark.

Both tray apps used to wear a dark palette unconditionally, so on a light
Windows desktop the tray menu and every dialog came up dark against light
windows (field, 2026-09-07).  This is the platform half of the fix: a plain
"what does the OS say" reader, Qt-free so the decision can be unit-tested
without an application, and `resolve_theme()` — the pure rule that folds the
user's own setting over it.

Each platform is best-effort and **never raises**: a desktop that does not
answer (an unknown Linux session, a locked-down registry) reports `None`, and
`resolve_theme` then falls back to `FALLBACK` — dark, which is what the app has
always looked like, so a failed detection changes nothing rather than flipping
somebody's tray to a theme they did not ask for.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import time

THEME_AUTO = "auto"
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEMES = (THEME_AUTO, THEME_LIGHT, THEME_DARK)

#: What "auto" means when the OS does not say — the app's historical look.
FALLBACK = THEME_DARK

# The detection is re-run whenever the tray menu opens so a theme switch does not
# need a restart. On Windows that is a registry read; on macOS and Linux it is a
# subprocess (~20-30 ms), which is worth not paying on every open.
CACHE_TTL_S = 5.0

_log = logging.getLogger("polyhost.os_theme")
_cache = {"at": 0.0, "value": None}


def _run(argv):
    """One short command's stdout, or None if it failed in any way."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _detect_windows():
    # AppsUseLightTheme is the one that governs application windows — the thing
    # the user is comparing the tray menu against. (SystemUsesLightTheme is the
    # taskbar/Start colour and can differ.)
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        with key:
            value, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
    except (ImportError, OSError, ValueError):
        return None
    return THEME_LIGHT if value else THEME_DARK


def _detect_macos():
    # The key only EXISTS while dark mode is on, so a failed read means light.
    out = _run(["defaults", "read", "-g", "AppleInterfaceStyle"])
    if out is None:
        return THEME_LIGHT
    return THEME_DARK if "dark" in out.lower() else THEME_LIGHT


def _detect_linux():
    # The freedesktop-ish answer first: GNOME/GTK's colour-scheme preference,
    # which KDE and several others also set. 'default' means "no preference",
    # so fall through to the theme NAME, which is how a dark GTK theme was
    # expressed before color-scheme existed.
    out = _run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"])
    if out:
        low = out.lower()
        if "dark" in low:
            return THEME_DARK
        if "light" in low:
            return THEME_LIGHT
    name = _run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"])
    if name and "dark" in name.lower():
        return THEME_DARK
    if name:
        return THEME_LIGHT
    return None


def detect_os_theme(use_cache: bool = True):
    """`"light"` / `"dark"`, or None when this desktop does not say."""
    now = time.monotonic()
    if use_cache and _cache["value"] is not None and now - _cache["at"] < CACHE_TTL_S:
        return _cache["value"]
    try:
        if sys.platform.startswith("win"):
            value = _detect_windows()
        elif sys.platform == "darwin":
            value = _detect_macos()
        else:
            value = _detect_linux()
    except Exception as exc:                      # noqa: BLE001 - cosmetic, never fatal
        _log.debug("OS theme detection failed: %s", exc)
        value = None
    _cache["at"], _cache["value"] = now, value
    return value


def forget_detected():
    """Drop the cached detection — for tests, and after a settings change."""
    _cache["at"], _cache["value"] = 0.0, None


def resolve_theme(setting, detected=None) -> str:
    """The theme to apply: the user's explicit choice, else what the OS says,
    else `FALLBACK`.  Pure — `detected` is passed in so the rule is testable
    without a desktop."""
    choice = str(setting or "").strip().lower()
    if choice in (THEME_LIGHT, THEME_DARK):
        return choice
    if choice and choice != THEME_AUTO:
        _log.warning("Unknown ui_theme %r — treating it as %r", setting, THEME_AUTO)
    return detected if detected in (THEME_LIGHT, THEME_DARK) else FALLBACK
