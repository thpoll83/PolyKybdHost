"""The PolyKybd Window Reporter GNOME Shell extension, installed from Integrations.

On GNOME/Wayland the host reads the focused window from this extension over
D-Bus (``handler/gnome_wayland_reporter.py``); without it only X11/XWayland
windows are seen. Integrations -> GNOME installs it, so nobody has to clone a
repository and edit GNOME's settings by hand.

What Install does:

- downloads ``extension.js`` and ``metadata.json`` from
  https://github.com/thpoll83/gnome-wayland-winreader at the commit pinned in
  ``EXTENSION_COMMIT``, and refuses a file whose SHA-256 is not the pinned one.
  The extension runs inside GNOME Shell, so the host installs exactly the reviewed
  version, never whatever the branch holds at install time. Moving the pin is a
  host change: update ``EXTENSION_COMMIT`` and ``EXTENSION_FILES`` together.
- writes them to ``$XDG_DATA_HOME/gnome-shell/extensions/<uuid>/`` (default
  ``~/.local/share``), the folder GNOME reads user extensions from,
- adds the uuid to ``org.gnome.shell enabled-extensions``. ``gnome-extensions
  enable`` would ask the running shell, which on Wayland does not know a new
  extension until the next login and refuses it, so the setting is written
  directly: the shell enables the extension at the next login.
- only when the user asks for it: sets ``org.gnome.shell
  disable-user-extensions`` to false. That setting switches off every user
  extension, so it is never changed as a side effect.

Remove deletes the two files (and the folder when it is then empty) and takes
the uuid out of ``enabled-extensions``. It leaves ``disable-user-extensions``
alone: other extensions may need it.

Every outside call (``gsettings``, ``gdbus``, the download) is passed in, so the
tests run without GNOME or a network.
"""
from __future__ import annotations

import ast
import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

UUID = "window-reporter@polykybd.org"
REPO = "thpoll83/gnome-wayland-winreader"
EXTENSION_COMMIT = "93a08bc59cdaa384db5511a81bc948ab5c4ce4f3"
# File name -> SHA-256 of that file at EXTENSION_COMMIT.
EXTENSION_FILES = {
    "extension.js": "a25d92eba890ffc9c68313d5f912682441386ccf4c95be2980ee49580863de27",
    "metadata.json": "541fb42918a89b9303f370743ed5e4dff691c4379ca1457ab1bbabf25dbf3655",
}
# Larger than either file by far; a bigger answer is not the extension.
MAX_FILE_BYTES = 64 * 1024
DOWNLOAD_TIMEOUT_S = 15
COMMAND_TIMEOUT_S = 3

SCHEMA = "org.gnome.shell"
KEY_ENABLED = "enabled-extensions"
KEY_DISABLED = "disabled-extensions"
KEY_USER_OFF = "disable-user-extensions"

DBUS_DEST = "org.gnome.Shell"
DBUS_PATH = "/org/polykybd/WindowReporter"
DBUS_IFACE = "org.polykybd.WindowReporter"

# Install/remove result messages; the GUI translates them (gnome_extension_page.py).
MSG_INSTALLED = "installed"
MSG_UPDATED = "updated"
MSG_UP_TO_DATE = "up-to-date"
MSG_REMOVED = "removed"
MSG_NOT_INSTALLED = "not-installed"
MSG_USER_ON = "user-extensions-on"
MSG_FAILED = "failed"


def file_url(name, commit=EXTENSION_COMMIT):
    return f"https://raw.githubusercontent.com/{REPO}/{commit}/{name}"


def is_gnome(env=None, platform=None):
    """True on a Linux desktop whose XDG_CURRENT_DESKTOP names GNOME
    (``GNOME``, ``ubuntu:GNOME``, ``GNOME-Classic:GNOME``)."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if not platform.startswith("linux"):
        return False
    desktops = (env.get("XDG_CURRENT_DESKTOP") or "").upper().split(":")
    return any(d.startswith("GNOME") for d in desktops)


def is_wayland(env=None):
    env = os.environ if env is None else env
    return (env.get("XDG_SESSION_TYPE") or "").lower() == "wayland"


def extension_dir(home=None, env=None):
    env = os.environ if env is None else env
    data = env.get("XDG_DATA_HOME") or os.path.join(home or os.path.expanduser("~"),
                                                    ".local", "share")
    return Path(data) / "gnome-shell" / "extensions" / UUID


@dataclass
class Status:
    folder: Path
    # The files in the folder: "missing", "current" (the pinned version) or
    # "other" (another version, or edited).
    files: str
    enabled: bool | None        # uuid in enabled-extensions; None: gsettings failed
    user_off: bool | None       # disable-user-extensions; None: gsettings failed
    user_off_writable: bool | None
    active: bool | None         # the D-Bus object answers; None: gdbus missing
    wayland: bool
    error: str = ""             # why a gsettings read failed


@dataclass
class Result:
    message: str
    detail: str = ""
    changed: bool = False


def _run(cmd, run):
    return run(cmd, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_S)


def parse_strv(text):
    """gsettings prints a string list as ``['a', 'b']``, an empty one as ``@as []``."""
    text = (text or "").strip()
    if text.startswith("@as"):
        text = text[3:].strip()
    value = ast.literal_eval(text) if text else []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"not a string list: {text!r}")
    return value


def format_strv(values):
    return "[" + ", ".join("'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
                           for v in values) + "]"


def _get(key, run):
    cp = _run(["gsettings", "get", SCHEMA, key], run)
    if cp.returncode != 0:
        raise RuntimeError((cp.stderr or cp.stdout or "gsettings failed").strip())
    return cp.stdout.strip()


def _set(key, value, run):
    cp = _run(["gsettings", "set", SCHEMA, key, value], run)
    if cp.returncode != 0:
        raise RuntimeError((cp.stderr or cp.stdout or "gsettings failed").strip())


def _files_state(folder):
    present = [folder / name for name in EXTENSION_FILES]
    if not any(p.exists() for p in present):
        return "missing"
    for path, digest in zip(present, EXTENSION_FILES.values()):
        try:
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                return "other"
        except OSError:
            return "other"
    return "current"


def _active(run):
    try:
        cp = _run(["gdbus", "call", "--session", "--dest", DBUS_DEST, "--object-path",
                   DBUS_PATH, "--method", f"{DBUS_IFACE}.GetFocusedWindow"], run)
    except FileNotFoundError:
        return None
    except (OSError, subprocess.SubprocessError):
        return False
    return cp.returncode == 0


def status(home=None, env=None, run=subprocess.run):
    folder = extension_dir(home, env)
    enabled = user_off = writable = None
    error = ""
    try:
        enabled = UUID in parse_strv(_get(KEY_ENABLED, run))
        user_off = _get(KEY_USER_OFF, run) == "true"
        cp = _run(["gsettings", "writable", SCHEMA, KEY_USER_OFF], run)
        writable = cp.returncode == 0 and cp.stdout.strip() == "true"
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError, SyntaxError) as exc:
        error = str(exc)
    return Status(folder=folder, files=_files_state(folder), enabled=enabled,
                  user_off=user_off, user_off_writable=writable, active=_active(run),
                  wayland=is_wayland(env), error=error)


def download(name, fetch=None):
    """The pinned file's bytes; raises ValueError when they do not match the pin."""
    if fetch is None:
        fetch = _fetch
    data = fetch(file_url(name))
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"{name}: {len(data)} bytes, more than {MAX_FILE_BYTES}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXTENSION_FILES[name]:
        raise ValueError(f"{name}: SHA-256 {digest} is not the pinned "
                         f"{EXTENSION_FILES[name]}")
    return data


def _fetch(url):
    import urllib.request
    from polyhost.util.https import ssl_context
    request = urllib.request.Request(url, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_S,
                                context=ssl_context()) as response:
        return response.read(MAX_FILE_BYTES + 1)


def _write_atomic(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def install(extension=True, user_extensions=False, home=None, env=None,
            run=subprocess.run, fetch=None):
    """Install the extension and/or switch user extensions on. Returns Results."""
    results = []
    if extension:
        folder = extension_dir(home, env)
        before = _files_state(folder)
        try:
            if before != "current":
                # Download both before writing either, so a failed download
                # never leaves half an extension in the folder.
                blobs = {name: download(name, fetch) for name in EXTENSION_FILES}
                folder.mkdir(parents=True, exist_ok=True)
                for name, data in blobs.items():
                    _write_atomic(folder / name, data)
            enabled = parse_strv(_get(KEY_ENABLED, run))
            if UUID not in enabled:
                _set(KEY_ENABLED, format_strv(enabled + [UUID]), run)
            disabled = parse_strv(_get(KEY_DISABLED, run))
            if UUID in disabled:
                _set(KEY_DISABLED, format_strv([d for d in disabled if d != UUID]), run)
            if before == "current":
                results.append(Result(MSG_UP_TO_DATE, str(folder),
                                      changed=UUID not in enabled))
            else:
                results.append(Result(MSG_INSTALLED if before == "missing" else MSG_UPDATED,
                                      str(folder), changed=True))
        except Exception as exc:  # noqa: BLE001 - reported on the page
            results.append(Result(MSG_FAILED, str(exc)))
    if user_extensions:
        try:
            _set(KEY_USER_OFF, "false", run)
            results.append(Result(MSG_USER_ON, changed=True))
        except Exception as exc:  # noqa: BLE001 - reported on the page
            results.append(Result(MSG_FAILED, str(exc)))
    return results


def remove(home=None, env=None, run=subprocess.run):
    folder = extension_dir(home, env)
    try:
        removed = False
        for name in EXTENSION_FILES:
            path = folder / name
            if path.exists():
                path.unlink()
                removed = True
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
        enabled = parse_strv(_get(KEY_ENABLED, run))
        if UUID in enabled:
            _set(KEY_ENABLED, format_strv([e for e in enabled if e != UUID]), run)
            removed = True
        return [Result(MSG_REMOVED if removed else MSG_NOT_INSTALLED, str(folder),
                       changed=removed)]
    except Exception as exc:  # noqa: BLE001 - reported on the page
        return [Result(MSG_FAILED, str(exc))]
