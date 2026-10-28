"""Overlay art read from games installed on this machine.

An overlay-mapping entry opts in with ``game_assets: <spec>``, a path under
``res/overlay_sources``; the spec's ``game_assets:`` block names the reader and
what it draws on each key (``build.py``). Game files may not be shipped, so the
reader draws from the user's own install, the copy is written to the user's
cache directory, and it is only ever sent to the keyboard.

Nothing is read at start. The first time an opted-in overlay is sent,
``request()`` builds the copy on a background thread, with the folder of the
game's executable as the first place to look; the shipped template goes out
meanwhile. When the copy is ready, ``take_changed()`` tells the window tick to
send the overlay again. ``override_for()`` gives the send path the copy.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from polyhost.services.game_assets.readers import all_settings

log = logging.getLogger("PolyHost")

# Settings this package reads; a change to any of them rebuilds the copies.
SETTING_KEYS = frozenset({"game_assets_enabled"} | {s.key for s in all_settings()})

_SOURCES = Path(__file__).resolve().parents[2] / "res" / "overlay_sources"

_specs: dict[str, Path] = {}         # template -> spec, from the overlay mapping
_overrides: dict[str, str] = {}      # template -> built copy
_started: dict[str, int] = {}        # template -> generation of its newest build
_lock = threading.Lock()
_generation = 0
# Set when the copies changed, so the window owner re-sends what is on the keyboard.
_changed = threading.Event()


def register_mapping(mapping: dict) -> None:
    """Remember which templates the overlay mapping opts in, and their specs."""
    specs = {}
    for entry in (mapping or {}).values():
        if isinstance(entry, dict) and entry.get("game_assets") and entry.get("overlay"):
            for template in entry["overlay"] if isinstance(entry["overlay"], list) else [entry["overlay"]]:
                specs[str(template)] = _SOURCES / str(entry["game_assets"])
    with _lock:
        _specs.clear()
        _specs.update(specs)


def override_for(template: str) -> str | None:
    """The path to send instead of the shipped `template`, or None."""
    return _overrides.get(template)


def take_changed() -> bool:
    """Whether the copies changed since the last call; clears the flag."""
    if _changed.is_set():
        _changed.clear()
        return True
    return False


def cache_dir() -> Path:
    import platformdirs
    return Path(platformdirs.user_cache_dir("PolyKybdHost")) / "game_overlays"


def request(template: str, settings_get, hint=None) -> threading.Thread | None:
    """Build the copy of `template` on a background thread unless it is built
    or building. An attempt that found no game files is retried on the next send. `hint` is the folder of the game's executable, or a callable
    returning it, read on the build thread. Returns the thread, or None."""
    global _generation
    spec = _specs.get(str(template))
    if spec is None or not settings_get("game_assets_enabled"):
        return None
    with _lock:
        if template in _started:
            return None
        _generation += 1
        mine = _started[template] = _generation

    def run():
        path = None
        try:
            from polyhost.services.game_assets import build
            path = build.build(template, spec, settings_get, cache_dir(),
                               hint() if callable(hint) else hint)
            if path is None:
                log.info("Game art: no game files for %s; using the shipped overlay.", template)
        except Exception as e:  # noqa: BLE001 — unreadable or unexpected game files
            log.warning("Game art: could not read the game files for %s (%s: %s); "
                        "using the shipped overlay.", template, type(e).__name__, e)
        with _lock:
            if _started.get(template) != mine:
                return                       # a newer request superseded this one
            old = _overrides.get(template)
            if path:
                _overrides[template] = str(path)
            else:
                _overrides.pop(template, None)
                # Try again on the next send: it may bring the game's folder
                # (a forwarded window has none), or the game was installed since.
                del _started[template]
            if _overrides.get(template) != old:
                _changed.set()

    t = threading.Thread(target=run, name="game-assets", daemon=True)
    t.start()
    return t


def reset(settings_get) -> None:
    """A setting changed: the next send of each overlay builds again. With the
    feature off, the copies are dropped at once."""
    if not (_started or _overrides):
        return                               # no opted-in overlay was sent yet
    enabled = settings_get("game_assets_enabled")
    with _lock:
        _started.clear()
        if not enabled:
            _overrides.clear()
    # Re-send what is on the keyboard; that send requests the rebuild.
    _changed.set()
