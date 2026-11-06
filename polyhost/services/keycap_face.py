"""A keycap face per application: an overlay-mapping entry may ask for a glyph
script and its placement while that application is in front.

    x64sc,x64sc.exe:
      overlay: vice_template.mods.png
      glyph_script: c64keys            # a GlyphScript name
      glyph_script_position: top-left  # centre or top-left (firmware protocol 26+)

Either key may be given alone. A key goes on the entry that matches, so on a
``titles-contains`` sub-entry when the overlay is there: the matcher hands back
the sub-entry, not its parent.

The keyboard stores the face it was last given and saves it at suspend, so an
override that is never undone would outlive the application, a host crash and a
reboot. So before the first override this remembers the user's own face, in
memory and in a small JSON file next to settings.yaml, and gives it back when
the application leaves the front, at shutdown, and on the next connect if the
file is still there (the host stopped while an override was on).

Qt-free and device-free: the caller passes a device object with four methods
(``get_glyph_script``, ``set_glyph_script``, ``get_glyph_placement``,
``set_glyph_placement``, the ``PolyKybd`` ones) and calls ``apply`` on the
thread that owns the device.
"""
from __future__ import annotations

import json
import logging
import os
import threading

from polyhost.device.command_ids import GlyphPlacement, GlyphScript

RESTORE_FILENAME = "keycap_face_restore.json"

_SCRIPTS = {s.name.lower(): s.value for s in GlyphScript}
_PLACES = {"centre": GlyphPlacement.CENTRE.value, "center": GlyphPlacement.CENTRE.value,
           "top-left": GlyphPlacement.TOP_LEFT.value, "top_left": GlyphPlacement.TOP_LEFT.value}


def restore_path() -> str:
    """Beside settings.yaml."""
    from polyhost.settings import settings_path
    return os.path.join(os.path.dirname(settings_path()), RESTORE_FILENAME)


def wanted_face(entry, log: logging.Logger | None = None):
    """The ``(script, placement)`` a mapping entry asks for, either part None when
    the entry leaves it alone; None when it asks for nothing (or only for values
    this host does not know, which are logged once per call and ignored)."""
    if not isinstance(entry, dict):
        return None
    raw_script, raw_place = entry.get("glyph_script"), entry.get("glyph_script_position")
    if raw_script is None and raw_place is None:
        return None
    script = place = None
    if raw_script is not None:
        script = _SCRIPTS.get(str(raw_script).strip().lower())
        if script is None and log:
            log.warning("Unknown glyph_script %r in the overlay mapping (known: %s).",
                        raw_script, ", ".join(sorted(_SCRIPTS)))
    if raw_place is not None:
        place = _PLACES.get(str(raw_place).strip().lower())
        if place is None and log:
            log.warning("Unknown glyph_script_position %r in the overlay mapping "
                        "(centre or top-left).", raw_place)
    if script is None and place is None:
        return None
    return script, place


class KeycapFace:
    """Applies and undoes the per-application face. Not thread-safe by itself:
    every method is called on the device worker, except ``note_user_choice``,
    which only touches the remembered face under a lock."""

    def __init__(self, path: str | None = None, log: logging.Logger | None = None):
        self._path = path
        self.log = log or logging.getLogger("PolyHost")
        self._lock = threading.Lock()
        self._active = None      # the (script, place) on the keyboard for an app, or None
        self._user = self._load()  # the user's own (script, place), while an override is on

    # --- the remembered face ---------------------------------------------------
    def _load(self):
        if not self._path:
            return None
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            return int(data["script"]), (None if data.get("place") is None else int(data["place"]))
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError) as e:
            self.log.warning("Ignoring an unreadable %s: %s", RESTORE_FILENAME, e)
            return None

    def _save(self, user):
        if not self._path:
            return
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"script": user[0], "place": user[1]}, f)
            os.replace(tmp, self._path)
        except OSError as e:
            self.log.warning("Could not store the keycap face to restore: %s", e)

    def _forget(self):
        self._user = None
        if self._path:
            try:
                os.remove(self._path)
            except FileNotFoundError:
                pass
            except OSError as e:
                self.log.warning("Could not remove %s: %s", RESTORE_FILENAME, e)

    @property
    def active(self):
        return self._active

    @property
    def remembered(self):
        return self._user

    # --- device side -------------------------------------------------------------
    @staticmethod
    def _read(dev):
        ok, script = dev.get_glyph_script()
        if not ok:
            return None
        ok, place = dev.get_glyph_placement()
        return int(script), (int(place) if ok else None)

    def _write(self, dev, script, place) -> bool:
        if script is not None:
            ok, msg = dev.set_glyph_script(script)
            if not ok:
                self.log.warning("Keycap face: could not set glyph script %s: %s", script, msg)
                return False
        if place is not None:
            ok, msg = dev.set_glyph_placement(place)
            if not ok:
                # Firmware below protocol 26: the script still applies.
                self.log.info("Keycap face: placement %s not set: %s", place, msg)
        return True

    def apply(self, wanted, dev) -> None:
        """Make the keyboard show `wanted` (from ``wanted_face``), or the user's own
        face when `wanted` is None. A no-op when nothing changes, so it is cheap to
        call on every window tick."""
        if wanted == self._active:
            return
        if wanted is None:
            self._restore(dev)
            return
        with self._lock:
            user = self._user
        if user is None:
            user = self._read(dev)
            if user is None:
                self.log.info("Keycap face: the keyboard did not report its glyph script; "
                              "leaving it as it is.")
                self._active = wanted        # do not retry on every tick
                return
            with self._lock:
                self._user = user
            self._save(user)
        # A part the entry leaves alone is the user's own, not whatever the
        # previous application asked for.
        script = user[0] if wanted[0] is None else wanted[0]
        place = user[1] if wanted[1] is None else wanted[1]
        if self._write(dev, script, place):
            self.log.info("Keycap face for this application: script %s, placement %s "
                          "(the user's own %s/%s is restored when it leaves).",
                          script, place, user[0], user[1])
        self._active = wanted

    def _restore(self, dev) -> None:
        with self._lock:
            user = self._user
        self._active = None
        if user is None:
            return
        if self._write(dev, user[0], user[1]):
            self.log.info("Keycap face restored: script %s, placement %s.", user[0], user[1])
            with self._lock:
                self._forget()

    def restore(self, dev) -> None:
        """Give the user's own face back now (shutdown, or a connect that finds a
        face left over from a host that stopped mid-override)."""
        self._restore(dev)

    def note_disconnected(self) -> None:
        """The keyboard is gone: what it shows is no longer known, so the next
        tick that wants a face sends it again. The remembered face stays."""
        self._active = None

    def note_user_choice(self, script=None, place=None) -> None:
        """The user picked a face by hand (tray, polyctl) while an application's
        face is on: that is now the face to restore."""
        with self._lock:
            if self._user is None:
                return
            user = (self._user[0] if script is None else int(script),
                    self._user[1] if place is None else int(place))
            self._user = user
        self._save(user)
