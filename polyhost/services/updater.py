"""GitHub-backed auto-updater for PolyKybdHost.

Polls the GitHub releases API for a newer version, downloads the auto-generated
source tarball, copies the files over the install directory, and triggers an
in-process restart. Designed for source-from-checkout installs on Win/Mac/Linux.
"""
import json
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

import platformdirs
import requests
from PyQt5.QtCore import QThread, pyqtSignal
from packaging.version import InvalidVersion, Version

import polyhost
from polyhost._version import __version__

log = logging.getLogger(__name__)

GITHUB_API    = "https://api.github.com/repos/thpoll83/PolyKybdHost/releases/latest"
GITHUB_FW_API = "https://api.github.com/repos/thpoll83/qmk_firmware/releases/latest"
USER_AGENT = f"PolyKybdHost/{__version__}"
HTTP_TIMEOUT = 5

# Persists ETag values across restarts so conditional requests (If-None-Match)
# return 304 Not Modified without counting against GitHub's rate limit.
_ETAG_CACHE = Path(platformdirs.user_cache_dir("PolyKybdHost")) / "update_etags.json"


def _load_etag_cache() -> dict:
    try:
        data = json.loads(_ETAG_CACHE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("ETag cache root must be an object")
        for key in ("host", "fw"):
            if key in data and not isinstance(data[key], dict):
                data.pop(key)
        return data
    except (OSError, ValueError):
        return {}


def _save_etag_cache(data: dict) -> None:
    try:
        _ETAG_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _ETAG_CACHE.write_text(json.dumps(data), encoding="utf-8")
    except OSError as e:
        log.debug("Could not save update ETag cache: %s", e)
DOWNLOAD_CHUNK = 64 * 1024

EXCLUDES = (
    ".venv", "venv", ".git", "__pycache__", "build", "dist",
    ".pytest_cache", ".idea", ".vscode", "*.log",
)


ReleaseInfo   = namedtuple("ReleaseInfo",   ["tag", "version", "tarball_url", "html_url"])
FwUpReleaseInfo = namedtuple("FwUpReleaseInfo", ["tag", "version", "bin_url", "uf2_url", "html_url"])


class UpdateCheckError(RuntimeError):
    """Raised when the GitHub releases API is unreachable or returns an unexpected response.

    Distinct from returning None (which means "API succeeded but no newer version exists").
    """


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
    """Return ReleaseInfo if GitHub's latest release is strictly newer; else None.

    Uses ETag caching: conditional requests that receive 304 Not Modified do not
    count against GitHub's anonymous rate limit (60 req/hour per IP).

    Raises UpdateCheckError on network/API failure so callers can distinguish
    "check failed" from "no update available".
    """
    cache = _load_etag_cache()
    host = cache.get("host", {})

    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    if etag := host.get("etag"):
        headers["If-None-Match"] = etag

    try:
        resp = requests.get(GITHUB_API, headers=headers, timeout=HTTP_TIMEOUT)
    except requests.RequestException as e:
        raise UpdateCheckError(f"Network error: {e}") from e

    if resp.status_code == 304:
        # Release unchanged since last check — re-evaluate against current version.
        try:
            cached_ver = host.get("version")
            if cached_ver and Version(cached_ver) > _current_version():
                log.info("Update check (cached): new version available: %s -> %s",
                         __version__, cached_ver)
                return ReleaseInfo(
                    tag=host["tag"],
                    version=cached_ver,
                    tarball_url=host["tarball_url"],
                    html_url=host.get("html_url", ""),
                )
        except (KeyError, InvalidVersion) as e:
            log.warning("Corrupt ETag cache for host update — discarding: %s", e)
            cache.pop("host", None)
            _save_etag_cache(cache)
            return None
        log.debug("Update check (cached): current %s is up-to-date", __version__)
        return None

    if resp.status_code == 403:
        raise UpdateCheckError("GitHub rate limit reached — try again later")
    if resp.status_code != 200:
        raise UpdateCheckError(f"GitHub API returned HTTP {resp.status_code}")

    try:
        data = resp.json()
        tag = data["tag_name"]
        tarball_url = data["tarball_url"]
        html_url = data.get("html_url", "")
    except (ValueError, KeyError) as e:
        raise UpdateCheckError(f"Malformed GitHub response: {e}") from e

    version_str = tag.lstrip("vV")
    try:
        latest = Version(version_str)
    except InvalidVersion:
        raise UpdateCheckError(f"Release tag {tag!r} is not a valid version") from None

    # Persist the ETag and release info for future conditional requests.
    cache["host"] = {
        "etag": resp.headers.get("ETag", ""),
        "tag": tag,
        "version": str(latest),
        "tarball_url": tarball_url,
        "html_url": html_url,
    }
    _save_etag_cache(cache)

    if latest <= _current_version():
        log.debug("Update check: current %s is up-to-date (latest %s)", __version__, latest)
        return None

    log.info("Update check: new version available: %s -> %s", __version__, latest)
    return ReleaseInfo(tag=tag, version=str(latest), tarball_url=tarball_url, html_url=html_url)


def check_fw_latest(current_version: str) -> Optional[FwUpReleaseInfo]:
    """Return FwUpReleaseInfo if the latest firmware release is strictly newer; else None.

    Uses ETag caching — 304 Not Modified responses don't count against the rate limit.
    Raises UpdateCheckError on network/API failure.
    Returns None for "up to date" or "release has no .bin asset".
    """
    try:
        current = Version(current_version.lstrip("vV"))
    except InvalidVersion:
        log.warning("Firmware update check: current version %r not parseable", current_version)
        return None

    cache = _load_etag_cache()
    fw = cache.get("fw", {})

    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    if etag := fw.get("etag"):
        headers["If-None-Match"] = etag

    try:
        resp = requests.get(GITHUB_FW_API, headers=headers, timeout=HTTP_TIMEOUT)
    except requests.RequestException as e:
        raise UpdateCheckError(f"Network error: {e}") from e

    if resp.status_code == 304:
        try:
            cached_ver = fw.get("version")
            if cached_ver and Version(cached_ver) > current and fw.get("bin_url"):
                log.info("Firmware update check (cached): new version available: %s -> %s",
                         current_version, cached_ver)
                return FwUpReleaseInfo(
                    tag=fw["tag"],
                    version=cached_ver,
                    bin_url=fw["bin_url"],
                    uf2_url=fw.get("uf2_url", ""),
                    html_url=fw.get("html_url", ""),
                )
        except (KeyError, InvalidVersion) as e:
            log.warning("Corrupt ETag cache for firmware update — discarding: %s", e)
            cache.pop("fw", None)
            _save_etag_cache(cache)
            return None
        log.debug("Firmware update check (cached): current %s is up-to-date", current_version)
        return None

    if resp.status_code == 403:
        raise UpdateCheckError("GitHub rate limit reached — try again later")
    if resp.status_code != 200:
        raise UpdateCheckError(f"GitHub API returned HTTP {resp.status_code}")

    try:
        data = resp.json()
        tag = data["tag_name"]
        html_url = data.get("html_url", "")
        assets = data.get("assets", [])
    except (ValueError, KeyError) as e:
        raise UpdateCheckError(f"Malformed GitHub response: {e}") from e

    version_str = tag.lstrip("vV")
    try:
        latest = Version(version_str)
    except InvalidVersion:
        raise UpdateCheckError(f"Release tag {tag!r} is not a valid version") from None

    bin_url = next((a["browser_download_url"] for a in assets if a["name"].endswith(".bin")), None)
    uf2_url = next((a["browser_download_url"] for a in assets if a["name"].endswith(".uf2")), None)

    # Cache ETag and asset URLs regardless of whether an update is available,
    # so future checks can use conditional requests.
    cache["fw"] = {
        "etag": resp.headers.get("ETag", ""),
        "tag": tag,
        "version": str(latest),
        "bin_url": bin_url or "",
        "uf2_url": uf2_url or "",
        "html_url": html_url,
    }
    _save_etag_cache(cache)

    if latest <= current:
        log.debug("Firmware update check: current %s is up-to-date (latest %s)", current_version, latest)
        return None

    if not bin_url:
        log.warning("Firmware update check: release %s has no .bin asset — skipping", tag)
        return None

    log.info("Firmware update check: new version available: %s -> %s", current_version, latest)
    return FwUpReleaseInfo(tag=tag, version=str(latest), bin_url=bin_url,
                           uf2_url=uf2_url or "", html_url=html_url)


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
        _indeterminate_sent = False
        with open(archive, "wb") as fh:
            for chunk in r.iter_content(DOWNLOAD_CHUNK):
                if not chunk:
                    continue
                fh.write(chunk)
                written += len(chunk)
                if progress_cb:
                    if total:
                        progress_cb(int(written * 100 / total))
                    elif not _indeterminate_sent:
                        progress_cb(-1)  # signal: no Content-Length → indeterminate
                        _indeterminate_sent = True

    extract_dir = tmpdir / "extracted"
    extract_dir.mkdir()
    with tarfile.open(archive, "r:gz") as tar:
        _safe_extract(tar, extract_dir)

    children = [p for p in extract_dir.iterdir() if p.is_dir()]
    if len(children) != 1:
        raise RuntimeError(f"Unexpected tarball layout: {[c.name for c in children]}")
    return children[0]


def _run_pip(args: list, label: str, line_cb=None) -> None:
    """Run `pip <args>` in the active interpreter; log on non-zero exit.

    Streams stdout+stderr line by line.  Each non-empty line is passed to
    ``line_cb(line)`` when provided, so callers can surface it as UI feedback.
    """
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "pip", *args],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        captured = []
        for raw in proc.stdout:
            line = raw.rstrip()
            if line:
                captured.append(line)
                if line_cb:
                    line_cb(line)
        proc.wait()
        if proc.returncode != 0:
            msg = (f"pip {label} after update returned {proc.returncode}: "
                   f'{" ".join(captured[-20:])[-500:]}')
            log.warning(msg)
            raise RuntimeError(msg)
    except (subprocess.SubprocessError, OSError) as e:
        raise RuntimeError(f"pip {label} after update failed to run: {e}") from e


# On Windows the running process holds native DLLs (e.g. hidapi.dll) open,
# so shutil.copy2 fails with WinError 32 when trying to overwrite them.
# apply_update() collects those files and returns them; UpdateInstaller
# writes this script to the temp dir, launches it detached, then quits.
# The relay waits for the app to exit (releasing DLL handles), copies the
# remaining files, relaunches, and cleans up.
_RELAY_SCRIPT_TEMPLATE = """\
import shutil, subprocess, sys, time

for src, dst in {pairs!r}:
    for attempt in range(4):
        try:
            shutil.copy2(src, dst)
            break
        except Exception as e:
            if attempt < 3:
                time.sleep(2)
            else:
                print(f"polyhost relay: {{e}}", file=sys.stderr)

subprocess.Popen({restart_args!r}, close_fds=False)
shutil.rmtree({tmp_dir!r}, ignore_errors=True)
"""


def _write_relay_script(locked: list, tmp_dir: Path) -> Path:
    """Write a detached relay script that copies locked files after app exit."""
    restart_args = [sys.executable, "-m", "polyhost", *sys.argv[1:]]
    script = tmp_dir / "_polyhost_relay.py"
    script.write_text(
        _RELAY_SCRIPT_TEMPLATE.format(
            pairs=locked,
            restart_args=restart_args,
            tmp_dir=str(tmp_dir),
        ),
        encoding="utf-8",
    )
    return script


def apply_update(extracted_dir: Path, install_root: Path, line_cb=None) -> list:
    """Copy files from `extracted_dir` over `install_root`, then refresh deps.

    On Windows, native DLLs locked by the running process are skipped and
    returned as a list of ``(src, dst)`` string pairs for deferred copy via
    a relay script.  On other platforms the list is always empty.

    Runs ``pip install -e .`` to pick up ``setup.py`` changes and, if a
    ``requirements.txt`` is present, ``pip install -r requirements.txt``.
    ``line_cb``, when provided, is called with each non-empty pip output line.
    """
    locked: list = []

    def _copy2(src, dst):
        try:
            shutil.copy2(src, dst)
        except OSError as e:
            if sys.platform == "win32" and getattr(e, "winerror", None) == 32:
                locked.append((str(src), str(dst)))
                log.debug("Deferring locked file: %s", src)
            else:
                raise

    shutil.copytree(
        extracted_dir,
        install_root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*EXCLUDES),
        copy_function=_copy2,
    )
    _run_pip(["install", "-e", str(install_root)], "install -e .", line_cb)
    requirements = install_root / "requirements.txt"
    if requirements.is_file():
        _run_pip(["install", "-r", str(requirements)], "install -r requirements.txt", line_cb)
    return locked


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
    """Background thread that polls GitHub for host and firmware updates."""

    update_available = pyqtSignal(object)    # ReleaseInfo
    fw_up_available  = pyqtSignal(object)    # FwUpReleaseInfo
    host_no_update   = pyqtSignal()          # host check found no newer release
    fw_no_update     = pyqtSignal()          # firmware check found no newer release
    error            = pyqtSignal(str)

    def __init__(self, current_fw_version: str = None, parent=None):
        super().__init__(parent)
        self._current_fw_version = current_fw_version

    def run(self):
        host_release = None
        fw_release   = None

        try:
            host_release = check_latest()
        except UpdateCheckError as e:
            log.warning("Host update check failed: %s", e)
            self.error.emit(str(e))
        except Exception as e:  # noqa: BLE001
            log.exception("Host update check crashed")
            self.error.emit(str(e))

        # Always emit host_no_update so the caller can reset its UI.  The error
        # signal fires first when the check failed, letting callers distinguish
        # "API/network error" from "genuinely no newer version".
        if host_release:
            self.update_available.emit(host_release)
        else:
            self.host_no_update.emit()

        if self._current_fw_version:
            try:
                fw_release = check_fw_latest(self._current_fw_version)
            except UpdateCheckError as e:
                log.warning("Firmware update check failed: %s", e)
                self.error.emit(str(e))
            except Exception as e:  # noqa: BLE001
                log.exception("Firmware update check crashed")
                self.error.emit(str(e))

            if fw_release:
                self.fw_up_available.emit(fw_release)
            else:
                self.fw_no_update.emit()


class UpdateInstaller(QThread):
    """Background thread that downloads, extracts, and applies an update."""

    progress    = pyqtSignal(int, str)
    finished_ok = pyqtSignal()
    relay_needed = pyqtSignal(str)  # path to relay script (Windows locked-file path)
    failed      = pyqtSignal(str)

    def __init__(self, release: ReleaseInfo, parent=None):
        super().__init__(parent)
        self.release = release

    def run(self):
        try:
            install_root = get_install_root()
        except NotWritableError as e:
            self.failed.emit(f"Install dir not writable: {e}")
            return

        # Use mkdtemp (not TemporaryDirectory context manager) so that on Windows
        # we can leave the directory alive for the relay script to consume.
        tmp_dir = Path(tempfile.mkdtemp(prefix="polyhost-update-"))
        try:
            self.progress.emit(0, "Downloading...")
            extracted = download_and_extract(
                self.release.tarball_url, tmp_dir,
                progress_cb=lambda pct: self.progress.emit(pct, "Downloading..."),
            )
            self.progress.emit(-1, "Applying update...")
            locked = apply_update(
                extracted, install_root,
                line_cb=lambda line: self.progress.emit(-1, line),
            )
        except Exception as e:  # noqa: BLE001
            log.exception("Update install failed")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            self.failed.emit(str(e))
            return

        try:
            if locked:
                relay_path = _write_relay_script(locked, tmp_dir)
                log.info("Relay script written for %d locked file(s): %s", len(locked), relay_path)
                # Do NOT clean up tmp_dir — relay script needs the source files and
                # will delete the directory itself after copying them.
                self.relay_needed.emit(str(relay_path))
            else:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                self.finished_ok.emit()
        except Exception as e:  # noqa: BLE001
            log.exception("Preparing relay install failed")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            self.failed.emit(str(e))


class FwUpDownloader(QThread):
    """Download a firmware .bin from a GitHub release asset URL to a temp file."""

    progress = pyqtSignal(int, str)        # (percent, message)
    finished = pyqtSignal(bool, str, str)  # (ok, error_or_empty, bin_path_or_empty)

    def __init__(self, release: FwUpReleaseInfo, parent=None):
        super().__init__(parent)
        self.release = release

    def run(self):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="polykybd-fw-", suffix=".bin", delete=False
            ) as tmp:
                tmp_path = tmp.name
                self.progress.emit(0, "Connecting…")
                with requests.get(
                    self.release.bin_url,
                    headers={"User-Agent": USER_AGENT},
                    stream=True,
                    timeout=HTTP_TIMEOUT * 6,
                ) as r:
                    r.raise_for_status()
                    total = int(r.headers.get("Content-Length") or 0)
                    written = 0
                    for chunk in r.iter_content(DOWNLOAD_CHUNK):
                        if not chunk:
                            continue
                        tmp.write(chunk)
                        written += len(chunk)
                        if total:
                            pct = int(written * 100 / total)
                            self.progress.emit(pct, f"Downloading firmware… {written // 1024} / {total // 1024} KB")
                        else:
                            self.progress.emit(0, f"Downloading firmware… {written // 1024} KB")
        except Exception as e:  # noqa: BLE001
            log.exception("Firmware download failed")
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            self.finished.emit(False, str(e), "")
            return
        self.finished.emit(True, "", tmp_path)
