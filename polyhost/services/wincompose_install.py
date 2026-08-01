"""Fetch and launch the PolyKybd build of WinCompose (Windows only).

WinCompose is what lets the keyboard type arbitrary unicode on Windows: with it
running, ``get_input_method()`` reports :class:`InputMethod.WinCompose` and the
host tells the keyboard to emit compose sequences instead of the far more
limited native Windows path. It is a separate application, so a fresh Windows
box has PolyKybdHost but no WinCompose — hence the tray offering to install it
when :func:`polyhost.input.unicode_input.wincompose_running` is False.

The download deliberately reuses the updater's **web** (non-API) release
lookup: ``github.com/<repo>/releases/latest`` + the ``expanded_assets``
fragment are not subject to api.github.com's 60-requests/hour anonymous limit,
which the firmware/host update checks already share.

Qt-free by design (like every other ``services/`` module) so the resolution and
download logic is unit-testable and the GUI only wires callbacks to it.
"""
import logging
import os
import re
import sys
import tempfile
import threading
from typing import NamedTuple, Optional

import requests

from polyhost.services.updater import (
    HTTP_TIMEOUT, USER_AGENT, _latest_tag_via_web, release_asset_urls,
)

log = logging.getLogger(__name__)

# Our fork. Upstream is samhocevar/wincompose; we ship our own build because the
# PolyKybd sequences/behaviour live in it (see the wincompose repo).
WINCOMPOSE_REPO = "thpoll83/wincompose"
RELEASES_URL = f"https://github.com/{WINCOMPOSE_REPO}/releases/latest"

DOWNLOAD_CHUNK = 64 * 1024

# The Inno Setup installer is named "WinCompose-Setup-<version>.exe"
# (src/installer/installer.iss OutputBaseFilename). Match loosely — any .exe
# whose name carries "setup" — so a rename doesn't silently break the flow, and
# never match the portable .zip (which needs no installing).
_SETUP_RE = re.compile(r"setup", re.IGNORECASE)


class InstallerInfo(NamedTuple):
    """A resolved WinCompose installer download."""
    tag: str
    url: str
    filename: str


class DownloadCancelled(Exception):
    """The user aborted the installer download."""


def pick_installer_asset(urls) -> Optional[str]:
    """The setup .exe among a release's asset URLs, or None.

    Pure (no I/O) for testability. Prefers a name containing "setup"; falls back
    to any single .exe so a differently-named installer still works."""
    exes = [u for u in urls if u.lower().endswith(".exe")]
    if not exes:
        return None
    for url in exes:
        if _SETUP_RE.search(url.rsplit("/", 1)[-1]):
            return url
    return exes[0]


def find_installer() -> Optional[InstallerInfo]:
    """Resolve the latest WinCompose release's installer, or None.

    None means "no release, or no installer asset in it" — the caller should
    fall back to opening :data:`RELEASES_URL` in a browser rather than erroring,
    so the menu entry stays useful before the first release is published."""
    tag = _latest_tag_via_web(WINCOMPOSE_REPO)
    if not tag:
        log.info("WinCompose: no published release found for %s.", WINCOMPOSE_REPO)
        return None
    url = pick_installer_asset(release_asset_urls(WINCOMPOSE_REPO, tag))
    if not url:
        log.info("WinCompose: release %s has no installer (.exe) asset.", tag)
        return None
    return InstallerInfo(tag=tag, url=url, filename=url.rsplit("/", 1)[-1])


def launch_installer(path: str) -> tuple:
    """Start the downloaded installer and return ``(ok, error)``.

    Uses ``os.startfile`` (ShellExecute) so Windows raises the normal UAC prompt
    — the installer needs elevation and we deliberately do not try to acquire it
    ourselves. Returns immediately; the installer outlives this call, so the
    tray re-checks for the running process rather than waiting on an exit code."""
    if sys.platform != "win32":
        return False, "The WinCompose installer only runs on Windows."
    try:
        os.startfile(path)  # noqa: S606 — a file we just downloaded ourselves
    except OSError as e:
        log.exception("Could not launch the WinCompose installer")
        return False, str(e)
    return True, ""


def open_releases_page() -> None:
    """Open the WinCompose releases page in the default browser."""
    import webbrowser
    webbrowser.open(RELEASES_URL)


class InstallerDownloader(threading.Thread):
    """Download the WinCompose installer to a temp .exe.

    Mirrors :class:`polyhost.services.updater.FwUpDownloader` — callbacks fire on
    this thread:

    - ``on_progress(int, str)`` — percent (0 when the size is unknown) + message
    - ``on_finished(bool, str, str)`` — (ok, error_or_empty, path_or_empty)
    """

    def __init__(self, info: InstallerInfo, *,
                 on_progress=None, on_finished=None, cancel_flag: list = None):
        super().__init__(daemon=True)
        self.info = info
        self._on_progress = on_progress
        self._on_finished = on_finished
        # Single-element list; set cancel_flag[0] = True to abort. Only a temp
        # file is written and nothing is executed until the user confirms, so
        # aborting mid-download is always safe.
        self._cancel_flag = cancel_flag

    def _cancelled(self) -> bool:
        return self._cancel_flag is not None and self._cancel_flag[0]

    def _fire(self, cb, *args):
        if cb is None:
            return
        try:
            cb(*args)
        except Exception:  # noqa: BLE001 — a UI callback must not kill the download
            log.exception("WinCompose download callback failed")

    def run(self):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="wincompose-setup-", suffix=".exe", delete=False
            ) as tmp:
                tmp_path = tmp.name
                self._fire(self._on_progress, 0, "Connecting…")
                with requests.get(
                    self.info.url,
                    headers={"User-Agent": USER_AGENT},
                    stream=True,
                    timeout=HTTP_TIMEOUT * 6,
                ) as r:
                    r.raise_for_status()
                    total = int(r.headers.get("Content-Length") or 0)
                    written = 0
                    for chunk in r.iter_content(DOWNLOAD_CHUNK):
                        if self._cancelled():
                            raise DownloadCancelled()
                        if not chunk:
                            continue
                        tmp.write(chunk)
                        written += len(chunk)
                        if total:
                            self._fire(self._on_progress, int(written * 100 / total),
                                       f"Downloading WinCompose… "
                                       f"{written // 1024} / {total // 1024} KB")
                        else:
                            self._fire(self._on_progress, 0,
                                       f"Downloading WinCompose… {written // 1024} KB")
        except DownloadCancelled:
            _unlink(tmp_path)
            log.info("WinCompose download cancelled by user.")
            self._fire(self._on_finished, False, "Download cancelled.", "")
            return
        except Exception as e:  # noqa: BLE001
            log.exception("WinCompose download failed")
            _unlink(tmp_path)
            self._fire(self._on_finished, False, str(e), "")
            return
        self._fire(self._on_finished, True, "", tmp_path)


def _unlink(path) -> None:
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass
