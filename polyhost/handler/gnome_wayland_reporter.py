"""GNOME/Wayland active-window reporter (⚠️ UNTESTED on hardware).

``pywinctl`` reads the active window via X11/EWMH, which GNOME's Mutter does NOT
expose for native Wayland windows — so on GNOME-Wayland active-window detection
needs help from the compositor. This module queries a **GNOME Shell extension**
over D-Bus: *Window Calls* / *Window Calls Extended*
(``org.gnome.Shell.Extensions.Windows``), which must be installed and enabled on
the machine. Without it, ``getActiveWindow()`` returns ``None`` (warned once) and
window tracking degrades to off — but with a clear message instead of failing
silently the way bare ``pywinctl`` does under Wayland.

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
_PATH = "/org/gnome/Shell/Extensions/Windows"
_IFACE = "org.gnome.Shell.Extensions.Windows"
_TIMEOUT = 1.5

_warned = False  # warn at most once that the extension is missing/unreachable


def _warn_once(msg, *args):
    global _warned
    if not _warned:
        _log.warning("GNOME/Wayland window reporter: " + msg + " — install/enable the "
                     "'Window Calls' GNOME Shell extension, or use an Xorg session.",
                     *args)
        _warned = True


def _gdbus(method, *args):
    """Call a Windows-extension method via gdbus; returns the CompletedProcess."""
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


def getActiveWindow():
    try:
        res = _gdbus("List")
    except FileNotFoundError:
        _warn_once("gdbus not found")
        return None
    except subprocess.TimeoutExpired:
        _warn_once("window query timed out")
        return None
    if res.returncode != 0:
        _warn_once("window query failed (%s)", (res.stderr or "").strip() or "no extension?")
        return None
    try:
        windows = json.loads(_unwrap_gdbus_string(res.stdout))
    except (ValueError, TypeError) as e:
        _log.debug("GNOME/Wayland: malformed window list (transient): %s", e)
        return None

    focused = next((w for w in windows if w.get("focus")), None)
    if not focused:
        return None
    # Base "Window Calls" omits the title from List() (privacy); fetch on demand.
    if not focused.get("title") and focused.get("id") is not None:
        try:
            tr = _gdbus("GetTitle", str(focused["id"]))
            if tr.returncode == 0:
                focused["title"] = _unwrap_gdbus_string(tr.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return GnomeWin(focused)
