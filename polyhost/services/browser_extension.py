"""Copy the PolyKybd browser extension to a folder, for "Load unpacked".

The extension (`browser-extension/` in this repository, also in every user
install) is not in the browser stores yet. A Chromium browser (Chrome, Edge,
Brave, Vivaldi, Opera, Arc) loads it from a folder with Developer mode on. This
module writes that folder: the shared files, and the Chromium manifest as
`manifest.json` (what `browser-extension/build.sh` builds as dist/chromium).

The folder is remembered (`browser_extension.json` in the config folder). At the
next start after a host update, `update_if_outdated()` copies the newer version
there; the browser then runs it after Reload on the extension card or a browser
restart.

Firefox keeps an unsigned extension only until it restarts, so this is for
Chromium browsers only.

Qt-free: the tray dialog (gui/browser_extension_dialog.py) and tests call it.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile

log = logging.getLogger(__name__)

SOURCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "browser-extension")
FILES = ("background.js", "options.html", "options.js")
ICONS_DIR = "icons"
MANIFEST = "manifest.chromium.json"
# Written into the folder, so a later copy knows the folder is ours and never
# overwrites a folder with someone else's files.
MARKER = ".polykybd-extension"
STATE_FILE = "browser_extension.json"


class ExtensionError(Exception):
    pass


def source_version(source_dir: str = SOURCE_DIR) -> str:
    """The version of the extension this host ships, or '' when it has none."""
    return _manifest_version(os.path.join(source_dir, MANIFEST))


def installed_version(folder: str) -> str:
    """The version in a folder this module wrote, or ''."""
    return _manifest_version(os.path.join(folder, "manifest.json"))


def _manifest_version(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            version = json.load(fh).get("version")
    except (OSError, ValueError, AttributeError):
        return ""
    return version if isinstance(version, str) else ""


def deploy(folder: str, source_dir: str = SOURCE_DIR) -> str:
    """Write the extension to `folder` and return its version. The folder must
    be empty, missing, or one this module wrote before. Raises ExtensionError."""
    if not source_version(source_dir):
        raise ExtensionError(f"no browser extension in {source_dir}")
    folder = os.path.abspath(folder)
    if os.path.isdir(folder) and os.listdir(folder) \
            and not os.path.exists(os.path.join(folder, MARKER)):
        raise ExtensionError(f"{folder} contains other files; choose an empty folder")
    try:
        os.makedirs(folder, exist_ok=True)
        # The marker first: a copy that fails halfway leaves a folder this
        # module may write again.
        with open(os.path.join(folder, MARKER), "w", encoding="utf-8") as fh:
            fh.write("Written by PolyKybdHost (Install Browser Extension…). "
                     "Files here are replaced at host updates.\n")
        # Each file is written whole and then renamed, so a browser that reads
        # the folder during a copy never sees half a file.
        for name in FILES:
            _copy(os.path.join(source_dir, name), os.path.join(folder, name))
        icons = os.path.join(source_dir, ICONS_DIR)
        os.makedirs(os.path.join(folder, ICONS_DIR), exist_ok=True)
        for name in os.listdir(icons):
            if name.endswith(".png"):
                _copy(os.path.join(icons, name), os.path.join(folder, ICONS_DIR, name))
        # The manifest last: it holds the version, so a copy that stopped
        # before it (an exit during the start-up update) is done again.
        _copy(os.path.join(source_dir, MANIFEST), os.path.join(folder, "manifest.json"))
    except OSError as e:
        raise ExtensionError(f"could not write {folder}: {e}") from e
    return installed_version(folder)


def _copy(src: str, dst: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(dst), suffix=".tmp")
    os.close(fd)
    try:
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass    # already moved or never written
        raise


# ---- the remembered folder ---------------------------------------------------------

def _state_path() -> str:
    from polyhost.server import protocol
    return os.path.join(protocol._config_dir(), STATE_FILE)


def remembered_folder(path: str | None = None) -> str:
    try:
        with open(path or _state_path(), encoding="utf-8") as fh:
            folder = json.load(fh).get("folder")
    except (OSError, ValueError, AttributeError):
        return ""
    return folder if isinstance(folder, str) else ""


def remember_folder(folder: str, path: str | None = None) -> None:
    path = path or _state_path()
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        # Absolute, as deploy() resolves it: a later start runs in another folder.
        json.dump({"folder": os.path.abspath(folder)}, fh)
    os.replace(tmp, path)


def update_if_outdated(path: str | None = None, source_dir: str = SOURCE_DIR) -> str:
    """At host start: copy a newer extension into the remembered folder. Returns
    the new version, or '' when nothing was copied. Never raises."""
    folder = remembered_folder(path)
    if not folder or not os.path.exists(os.path.join(folder, MARKER)):
        return ""
    new = source_version(source_dir)
    if not new or new == installed_version(folder):
        return ""
    try:
        version = deploy(folder, source_dir)
    except ExtensionError as e:
        log.info("Browser extension: %s", e)
        return ""
    log.info("Browser extension: copied version %s to %s; click Reload on the "
             "extension card in the browser, or restart the browser", version, folder)
    return version
