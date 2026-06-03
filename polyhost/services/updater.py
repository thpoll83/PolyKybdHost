"""GitHub-backed auto-updater for PolyKybdHost.

Polls the GitHub releases API for a newer version, downloads the auto-generated
source tarball, copies the files over the install directory, and triggers an
in-process restart. Designed for source-from-checkout installs on Win/Mac/Linux.
"""
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections import namedtuple
from pathlib import Path
from typing import Optional

import requests
from PyQt5.QtCore import QThread, pyqtSignal
from packaging.version import InvalidVersion, Version

import polyhost
from polyhost._version import __version__

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com/repos/thpoll83/PolyKybdHost/releases/latest"
USER_AGENT = f"PolyKybdHost/{__version__}"
HTTP_TIMEOUT = 5
DOWNLOAD_CHUNK = 64 * 1024

EXCLUDES = (
    ".venv", "venv", ".git", "__pycache__", "build", "dist",
    ".pytest_cache", ".idea", ".vscode", "*.log",
)


ReleaseInfo = namedtuple("ReleaseInfo", ["tag", "version", "tarball_url", "html_url"])


class NotWritableError(RuntimeError):
    """Raised when the install directory cannot be modified (e.g. system site-packages)."""


def get_install_root() -> Path:
    """Return the directory we'd overwrite (parent of the `polyhost` package)."""
    root = Path(polyhost.__file__).resolve().parent.parent
    if not os.access(root, os.W_OK):
        raise NotWritableError(str(root))
    return root


def _current_version() -> Version:
    return Version(__version__)


def check_latest() -> Optional[ReleaseInfo]:
    """Return ReleaseInfo if GitHub's latest release is strictly newer; else None."""
    try:
        resp = requests.get(
            GITHUB_API,
            headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException as e:
        log.warning("Update check failed (network): %s", e)
        return None

    if resp.status_code == 403:
        log.warning("Update check rate-limited by GitHub (HTTP 403)")
        return None
    if resp.status_code != 200:
        log.warning("Update check failed: HTTP %s", resp.status_code)
        return None

    try:
        data = resp.json()
        tag = data["tag_name"]
        tarball_url = data["tarball_url"]
        html_url = data.get("html_url", "")
    except (ValueError, KeyError) as e:
        log.warning("Update check: malformed release payload: %s", e)
        return None

    version_str = tag.lstrip("vV")
    try:
        latest = Version(version_str)
    except InvalidVersion:
        log.warning("Update check: tag %r is not a valid version", tag)
        return None

    if latest <= _current_version():
        log.debug("Update check: current %s is up-to-date (latest %s)", __version__, latest)
        return None

    log.info("Update check: new version available: %s -> %s", __version__, latest)
    return ReleaseInfo(tag=tag, version=str(latest), tarball_url=tarball_url, html_url=html_url)


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract `tar` into `dest`, refusing any path-traversal or link members.

    On Python >=3.12, delegates to the stdlib `filter="data"` extractor which
    enforces these constraints itself. On older Pythons, symlink and hardlink
    members are rejected outright (otherwise a tarball could plant a link
    under `dest` and have a later entry write through it to escape `dest`).
    """
    if sys.version_info >= (3, 12):
        tar.extractall(path=dest, filter="data")
        return
    dest_resolved = dest.resolve()
    for member in tar.getmembers():
        if member.issym() or member.islnk():
            raise RuntimeError(f"Refusing link tar member: {member.name}")
        target = (dest / member.name).resolve()
        if dest_resolved != target and dest_resolved not in target.parents:
            raise RuntimeError(f"Refusing unsafe tar member: {member.name}")
    tar.extractall(path=dest)


def download_and_extract(tarball_url: str, tmpdir: Path,
                         progress_cb=None) -> Path:
    """Download the tarball and extract it. Return the single top-level dir."""
    archive = tmpdir / "src.tar.gz"
    with requests.get(tarball_url,
                      headers={"User-Agent": USER_AGENT},
                      stream=True, timeout=HTTP_TIMEOUT * 6) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        written = 0
        with open(archive, "wb") as fh:
            for chunk in r.iter_content(DOWNLOAD_CHUNK):
                if not chunk:
                    continue
                fh.write(chunk)
                written += len(chunk)
                if progress_cb and total:
                    progress_cb(int(written * 100 / total))

    extract_dir = tmpdir / "extracted"
    extract_dir.mkdir()
    with tarfile.open(archive, "r:gz") as tar:
        _safe_extract(tar, extract_dir)

    children = [p for p in extract_dir.iterdir() if p.is_dir()]
    if len(children) != 1:
        raise RuntimeError(f"Unexpected tarball layout: {[c.name for c in children]}")
    return children[0]


def _run_pip(args: list, label: str) -> None:
    """Run `pip <args>` in the active interpreter; log on non-zero exit."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", *args],
            check=False, capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            details = (result.stderr or "").strip() or (result.stdout or "").strip()
            log.warning("pip %s after update returned %d: %s",
                        label, result.returncode, details[-500:])
    except (subprocess.SubprocessError, OSError) as e:
        log.warning("pip %s after update failed to run: %s", label, e)


def apply_update(extracted_dir: Path, install_root: Path) -> None:
    """Copy files from `extracted_dir` over `install_root`, then refresh deps.

    Runs `pip install -e .` to pick up `setup.py` changes and, if a
    `requirements.txt` is present, `pip install -r requirements.txt` so new
    runtime deps declared only there are installed into the active venv.
    """
    shutil.copytree(
        extracted_dir,
        install_root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*EXCLUDES),
    )
    _run_pip(["install", "-e", str(install_root)], "install -e .")
    requirements = install_root / "requirements.txt"
    if requirements.is_file():
        _run_pip(["install", "-r", str(requirements)], "install -r requirements.txt")


def restart_app() -> None:
    """Re-exec the app. Uses subprocess+exit on Windows (execv argv issues)."""
    args = [sys.executable, "-m", "polyhost", *sys.argv[1:]]
    log.info("Restarting: %s", args)
    if sys.platform == "win32":
        subprocess.Popen(args, close_fds=False)
        sys.exit(0)
    else:
        os.execv(sys.executable, args)


class UpdateChecker(QThread):
    """Background thread that polls GitHub once and emits the result."""

    update_available = pyqtSignal(object)
    no_update = pyqtSignal()
    error = pyqtSignal(str)

    def run(self):
        try:
            release = check_latest()
        except Exception as e:  # noqa: BLE001
            log.exception("Update check crashed")
            self.error.emit(str(e))
            return
        if release is None:
            self.no_update.emit()
        else:
            self.update_available.emit(release)


class UpdateInstaller(QThread):
    """Background thread that downloads, extracts, and applies an update."""

    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, release: ReleaseInfo, parent=None):
        super().__init__(parent)
        self.release = release

    def run(self):
        try:
            install_root = get_install_root()
        except NotWritableError as e:
            self.failed.emit(f"Install dir not writable: {e}")
            return

        try:
            with tempfile.TemporaryDirectory(prefix="polyhost-update-") as td:
                tmp = Path(td)
                self.progress.emit(0, "Downloading...")
                extracted = download_and_extract(
                    self.release.tarball_url, tmp,
                    progress_cb=lambda pct: self.progress.emit(pct, "Downloading..."),
                )
                self.progress.emit(100, "Applying update...")
                apply_update(extracted, install_root)
        except Exception as e:  # noqa: BLE001
            log.exception("Update install failed")
            self.failed.emit(str(e))
            return
        self.finished_ok.emit()
