"""Overlay art read from games installed on this machine.

Some shipped templates can be redrawn from the game's own files, which may not
be shipped (see `cnc_classic.py`). `start()` builds those copies on a background
thread into the user's cache directory; `override_for()` then tells the overlay
send which file to use in place of a shipped template. Until a copy is ready, or
when the game is not found, the shipped template is used.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

log = logging.getLogger("PolyHost")

# Settings this module reads; a change to any of them rebuilds the copies.
SETTING_KEYS = frozenset({"game_assets_enabled", "game_cnc_data_dir", "game_cnc_faction"})

_overrides: dict[str, str] = {}
_lock = threading.Lock()
_generation = 0


def override_for(template: str) -> str | None:
    """The path to send instead of the shipped `template`, or None."""
    return _overrides.get(template)


def cache_dir() -> Path:
    import platformdirs
    return Path(platformdirs.user_cache_dir("PolyKybdHost")) / "game_overlays"


def build_all(settings_get) -> dict[str, str]:
    """Build every copy this machine supports and return {template: path}.
    Runs on the caller's thread; a failure leaves the shipped template in use."""
    found = {}
    if not settings_get("game_assets_enabled"):
        return found
    try:
        from polyhost.services.game_assets import cnc_classic
        path = cnc_classic.build(cache_dir(), str(settings_get("game_cnc_data_dir") or ""),
                                 str(settings_get("game_cnc_faction") or "gdi").lower())
        if path:
            found[cnc_classic.TEMPLATE] = str(path)
        else:
            log.info("C&C game art: classic game files not found, using the shipped overlay.")
    except Exception as e:  # noqa: BLE001 — unreadable or unexpected game files
        log.warning("C&C game art: could not read the game files (%s: %s); "
                    "using the shipped overlay.", type(e).__name__, e)
    return found


def start(settings_get) -> threading.Thread:
    """Rebuild the copies on a background thread. A later call supersedes an
    earlier one: only the newest build's result is installed."""
    global _generation
    with _lock:
        _generation += 1
        mine = _generation

    def run():
        found = build_all(settings_get)
        with _lock:
            if mine == _generation:
                _overrides.clear()
                _overrides.update(found)

    t = threading.Thread(target=run, name="game-assets", daemon=True)
    t.start()
    return t
