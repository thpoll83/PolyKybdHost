"""GNOME/Wayland active-window reporter (⚠️ UNTESTED on hardware).

``pywinctl`` reads the active window via X11/EWMH, which GNOME's Mutter does NOT
expose for native Wayland windows — so on GNOME-Wayland active-window detection
needs help from the compositor. This module queries our own purpose-built,
**read-only** GNOME Shell extension over D-Bus: *PolyKybd Window Reporter*
(``org.polykybd.WindowReporter``, repo
https://github.com/thpoll83/gnome-wayland-winreader), which must be installed and
enabled on the machine. It exposes a single getter — ``GetFocusedWindow()`` — and
no window-modifying methods, unlike the general *Window Calls* extension it
replaces. Without it, ``getActiveWindow()`` **falls back to pywinctl
(X11/XWayland)** — so X11-backed apps (Chrome, VS Code, JetBrains, …) running
under XWayland are still tracked, though native Wayland windows are not — and
warns once. That beats bare ``pywinctl``'s silent Wayland failure, and means a
session that got flipped to Wayland by an OS update keeps tracking most apps.
The fallback imports pywinctl **lazily and guarded** (it can ``sys.exit()`` when
no X server is reachable), so the module still loads with zero pywinctl/Qt at
import time and stays headless-safe.

It mirrors the ``pywinctl`` / ``kde_win_reporter`` surface the callers
(``active_window.py``, ``forwarder.py``) use: ``getActiveWindow()`` returns an
object exposing ``.title``, ``.getHandle()``, ``.getAppName()`` and ``__eq__``,
or ``None``.

⚠️ **Untested**: there is no GNOME-Wayland environment in the dev/CI container,
so only the output parsing is unit-tested (``tests/handler/gnome_wayland_reporter_test.py``);
the live D-Bus call and the gdbus-escaping of exotic titles are validated only on
real hardware. The **X11 path is unaffected** — this module is selected only when
``XDG_SESSION_TYPE == "wayland"`` on a non-KDE desktop; X11 keeps using pywinctl.
"""
import json
import logging
import subprocess

_log = logging.getLogger("PolyHost")

_DEST = "org.gnome.Shell"
_PATH = "/org/polykybd/WindowReporter"
_IFACE = "org.polykybd.WindowReporter"
_TIMEOUT = 1.5

_warned = False  # warn at most once that the extension is missing/unreachable

# Lazily-imported pywinctl fallback (see _pywinctl_fallback). Module-level so the
# import is attempted once, not on every poll.
_pywinctl = None
_pywinctl_tried = False

# Sentinel: the extension is unavailable (caller should fall back), as opposed to
# the extension being up but reporting no focused window (a real None).
_UNAVAILABLE = object()


def _warn_once(msg, *args):
    global _warned
    if not _warned:
        _log.warning("GNOME/Wayland window reporter: " + msg + " — the 'PolyKybd Window "
                     "Reporter' GNOME Shell extension is unavailable; falling back to "
                     "X11/XWayland (native Wayland windows won't be tracked). Install it "
                     "from https://github.com/thpoll83/gnome-wayland-winreader and run "
                     "'gnome-extensions enable window-reporter@polykybd.org', or use an "
                     "Xorg session for full coverage.", *args)
        _warned = True


def _pywinctl_fallback():
    """Lazily import pywinctl as an XWayland fallback, guarded.

    pywinctl reads X11/EWMH, so under a Wayland session with XWayland running it
    still sees X11-backed windows (Chrome, VS Code, JetBrains, …) — just not
    native Wayland ones. The import is guarded because pywinctl/pymonctl can
    ``sys.exit()`` when no X server / xrandr is reachable, which must not take
    down the host or forwarder. Returns the module, or None if unavailable."""
    global _pywinctl, _pywinctl_tried
    if _pywinctl_tried:
        return _pywinctl
    _pywinctl_tried = True
    try:
        import pywinctl
        _pywinctl = pywinctl
        _log.info("GNOME/Wayland: using pywinctl (X11/XWayland) as the active-window "
                  "fallback — native Wayland windows won't be tracked.")
    except SystemExit:
        _log.warning("GNOME/Wayland: pywinctl fallback unavailable (no X server/XWayland "
                     "reachable).")
        _pywinctl = None
    except Exception as e:  # noqa: BLE001 — any import failure disables the fallback
        _log.warning("GNOME/Wayland: pywinctl fallback import failed: %s", e)
        _pywinctl = None
    return _pywinctl


def _gdbus(method, *args):
    """Call a WindowReporter method via gdbus; returns the CompletedProcess."""
    cmd = ["gdbus", "call", "--session", "--dest", _DEST,
           "--object-path", _PATH, "--method", f"{_IFACE}.{method}", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=_TIMEOUT)


def _unwrap_gdbus_string(stdout):
    """gdbus prints a single string return as ``('payload',)``. Strip the tuple
    wrapper and undo gdbus's single-quote/backslash escaping so the JSON parses.
    (Double quotes inside the JSON pass through untouched.)"""
    s = stdout.strip()
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1].rstrip(",").strip()
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        s = s[1:-1]
    return s.replace("\\\\", "\\").replace("\\'", "'")


class GnomeWin:
    """pywinctl/KWin-compatible window handle for one focused window."""

    def __init__(self, win):
        self._id = win.get("id")
        self.title = win.get("title") or ""
        self._wm_class = win.get("wm_class") or win.get("wm_class_instance") or ""

    def getHandle(self):
        return self._id

    def getAppName(self):
        return self._wm_class

    def __eq__(self, other):
        if other is None or not hasattr(other, "getHandle"):
            return False
        return self._id == other.getHandle()


def _query_extension():
    """Query the PolyKybd Window Reporter extension. Returns a :class:`GnomeWin`,
    ``None`` (extension is up but nothing is focused), or ``_UNAVAILABLE``
    (extension missing/unreachable — the caller should fall back to pywinctl)."""
    try:
        res = _gdbus("GetFocusedWindow")  # one round-trip; returns the title too
    except FileNotFoundError:
        _warn_once("gdbus not found")
        return _UNAVAILABLE
    except subprocess.TimeoutExpired:
        _warn_once("window query timed out")
        return _UNAVAILABLE
    if res.returncode != 0:
        _warn_once("window query failed (%s)", (res.stderr or "").strip() or "no extension?")
        return _UNAVAILABLE

    payload = _unwrap_gdbus_string(res.stdout)
    if payload == "null":
        return None  # extension is up; genuinely nothing focused — do NOT fall back
    try:
        win = json.loads(payload)
    except (ValueError, TypeError) as e:
        _log.debug("GNOME/Wayland: malformed focused-window payload (transient): %s", e)
        return _UNAVAILABLE
    return GnomeWin(win)


def getActiveWindow():
    win = _query_extension()
    if win is not _UNAVAILABLE:
        return win  # GnomeWin, or None when the extension is up but nothing focused
    # Extension unavailable — fall back to pywinctl so X11/XWayland apps are still
    # tracked (native Wayland windows are not visible to it).
    pwc = _pywinctl_fallback()
    if pwc is None:
        return None
    try:
        return pwc.getActiveWindow()
    except Exception as e:  # noqa: BLE001 — fallback must never raise into the poll
        _log.debug("GNOME/Wayland: pywinctl fallback getActiveWindow failed: %s", e)
        return None
