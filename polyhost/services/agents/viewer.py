"""Find the remote-desktop viewer window that shows another computer.

A key press on an agent from a forwarder's computer brings forward, on THIS
computer, the viewer window that shows that computer (NoMachine, Remote Desktop,
VNC, ...). The forwarder raises the agent's own window over there only when its
own setting `agents_raise_here` is on (services/agents/remote.py, HOST-6).

A viewer is a window of a known viewer app (VIEWER_APPS, plus every overlay
mapping entry marked `remote: true`). Among them the one whose title names the
computer is taken; with no such title and exactly one viewer open, that one.
"""
from __future__ import annotations

# Process / app names, lower case, without ".exe" or ".bin" (normalise_app).
VIEWER_APPS = frozenset({
    "nxplayer", "nomachine",                              # NoMachine
    "mstsc", "msrdc", "remote desktop connection",        # Microsoft Remote Desktop
    "microsoft remote desktop", "windows app",
    "vncviewer", "vnc viewer", "tvnviewer", "tigervnc", "xtigervncviewer",
    "realvnc", "ultravnc", "uvnc_viewer", "screen sharing",
    "remmina", "krdc", "vinagre", "gnome-connections", "connections",
    "parsecd", "parsec", "anydesk", "teamviewer", "rustdesk", "x2goclient",
})


def normalise_app(name: str) -> str:
    name = (name or "").strip().lower().replace("\\", "/").rsplit("/", 1)[-1]
    for suffix in (".exe", ".bin", ".app"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name


def mapping_viewer_apps(mapping) -> set[str]:
    """App names of overlay mapping entries marked `remote: true`."""
    out = set()
    for key, entry in (mapping or {}).items():
        if isinstance(entry, dict) and entry.get("remote"):
            out.update(normalise_app(n) for n in str(key).split(","))
    return out


def find_viewer(machine: str, windows, extra_apps=()):
    """The viewer window for `machine` among `windows`, or None. `windows` holds
    objects with getAppName() and title (pywinctl windows)."""
    apps = VIEWER_APPS | {normalise_app(a) for a in extra_apps}

    def app_of(w):
        try:
            return normalise_app(w.getAppName() or "")
        except Exception:   # noqa: BLE001 - a window can close while we read it
            return ""

    viewers = [w for w in windows if app_of(w) in apps]
    names = {n for n in ((machine or "").lower(), (machine or "").lower().split(".")[0]) if n}
    named = [w for w in viewers if any(n in (w.title or "").lower() for n in names)]
    if named:
        return named[0]
    return viewers[0] if len(viewers) == 1 else None
