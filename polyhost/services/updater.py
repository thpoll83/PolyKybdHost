"""GitHub-backed auto-updater for PolyKybdHost.

Polls the GitHub releases API for a newer version, downloads the auto-generated
source tarball, copies the files over the install directory, and triggers an
in-process restart. Designed for source-from-checkout installs on Win/Mac/Linux.
"""
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
from collections import namedtuple
from pathlib import Path
from typing import Optional

import platformdirs
import requests
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


def get_last_check_time() -> float:
    """Unix time of the last automatic update check (0.0 if never checked).

    Persisted (in the ETag cache file) so the check throttle survives restarts.
    The in-memory throttle reset on every launch, so frequent restarts each
    fired a check — and ETag/304 responses still count against GitHub's
    unauthenticated 60-requests/hour-per-IP limit, so that exhausted it
    (especially behind a shared office IP). Persisting the timestamp means a
    restart within the throttle window makes no request at all."""
    try:
        return float(_load_etag_cache().get("checked_at", 0.0))
    except (TypeError, ValueError):
        return 0.0


def set_last_check_time(ts: float) -> None:
    """Persist the unix time of the most recent automatic update check."""
    cache = _load_etag_cache()
    cache["checked_at"] = float(ts)
    _save_etag_cache(cache)


DOWNLOAD_CHUNK = 64 * 1024

EXCLUDES = (
    ".venv", "venv", ".git", "__pycache__", "build", "dist",
    ".pytest_cache", ".idea", ".vscode", "*.log",
)


ReleaseInfo   = namedtuple("ReleaseInfo",   ["tag", "version", "tarball_url", "html_url", "published_at"])
FwUpReleaseInfo = namedtuple("FwUpReleaseInfo", ["tag", "version", "bin_url", "uf2_url", "html_url", "published_at"])


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


# Release tags carry a repo-specific prefix before the version number: the host
# publishes ``vX.Y.Z`` while the firmware publishes ``PolyKybd-fw-vX.Y.Z``.
# Anchor on the first dotted-numeric run so a stray digit in the prefix isn't
# mistaken for the version; return from there to the end of the string so any
# trailing prerelease/build suffix is preserved for Version() to interpret.
_TAG_VERSION_RE = re.compile(r"\d+(?:\.\d+)+")


def _version_from_tag(tag: str) -> str:
    """Extract the version substring from a release tag.

    Handles plain ``1.2.3``, ``v1.2.3`` and prefixed tags such as the firmware
    repo's ``PolyKybd-fw-v0.8.3``, and preserves any prerelease/build suffix
    (``v1.2.3rc1`` -> ``1.2.3rc1``). Returns ``""`` when the tag contains no
    dotted-numeric version, which ``Version()`` then rejects uniformly.
    """
    match = _TAG_VERSION_RE.search(tag)
    return tag[match.start():] if match else ""


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
                    published_at=host.get("published_at", ""),
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
        published_at = data.get("published_at", "")
    except (ValueError, KeyError) as e:
        raise UpdateCheckError(f"Malformed GitHub response: {e}") from e

    version_str = _version_from_tag(tag)
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
        "published_at": published_at,
    }
    _save_etag_cache(cache)

    if latest <= _current_version():
        log.debug("Update check: current %s is up-to-date (latest %s)", __version__, latest)
        return None

    log.info("Update check: new version available: %s -> %s", __version__, latest)
    return ReleaseInfo(tag=tag, version=str(latest), tarball_url=tarball_url,
                       html_url=html_url, published_at=published_at)


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
                    published_at=fw.get("published_at", ""),
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
        published_at = data.get("published_at", "")
    except (ValueError, KeyError) as e:
        raise UpdateCheckError(f"Malformed GitHub response: {e}") from e

    version_str = _version_from_tag(tag)
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
        "published_at": published_at,
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
                           uf2_url=uf2_url or "", html_url=html_url, published_at=published_at)


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


def _fire(cb, *args):
    """Invoke ``cb(*args)`` if it is not None. Callbacks run on the worker thread.

    A None callback is silently skipped, so call sites only wire up the events
    they care about.
    """
    if cb is not None:
        cb(*args)


class UpdateChecker(threading.Thread):
    """Background thread that polls GitHub for host and firmware updates.

    Callbacks fire on this thread (not the caller's), so consumers that touch
    GUI state must marshal back to their own loop. They mirror the previous Qt
    signals one-to-one:

    - ``on_update_available(ReleaseInfo)`` — newer host release found
    - ``on_fw_up_available(FwUpReleaseInfo)`` — newer firmware release found
    - ``on_host_no_update()`` — host check found no newer release
    - ``on_fw_no_update()`` — firmware check found no newer release
    - ``on_error(str)`` — host/firmware check failed (network/API)
    """

    def __init__(self, current_fw_version: str = None, *,
                 on_update_available=None, on_fw_up_available=None,
                 on_host_no_update=None, on_fw_no_update=None, on_error=None):
        super().__init__(daemon=True)
        self._current_fw_version = current_fw_version
        self._on_update_available = on_update_available
        self._on_fw_up_available = on_fw_up_available
        self._on_host_no_update = on_host_no_update
        self._on_fw_no_update = on_fw_no_update
        self._on_error = on_error

    def run(self):
        host_release = None
        fw_release   = None

        try:
            host_release = check_latest()
        except UpdateCheckError as e:
            log.warning("Host update check failed: %s", e)
            _fire(self._on_error, str(e))
        except Exception as e:  # noqa: BLE001
            log.exception("Host update check crashed")
            _fire(self._on_error, str(e))

        # Always fire host_no_update so the caller can reset its UI.  The error
        # callback fires first when the check failed, letting callers distinguish
        # "API/network error" from "genuinely no newer version".
        if host_release:
            _fire(self._on_update_available, host_release)
        else:
            _fire(self._on_host_no_update)

        if self._current_fw_version:
            try:
                fw_release = check_fw_latest(self._current_fw_version)
            except UpdateCheckError as e:
                log.warning("Firmware update check failed: %s", e)
                _fire(self._on_error, str(e))
            except Exception as e:  # noqa: BLE001
                log.exception("Firmware update check crashed")
                _fire(self._on_error, str(e))

            if fw_release:
                _fire(self._on_fw_up_available, fw_release)
            else:
                _fire(self._on_fw_no_update)


class UpdateInstaller(threading.Thread):
    """Background thread that downloads, extracts, and applies an update.

    Callbacks fire on this thread; they mirror the previous Qt signals:

    - ``on_progress(int, str)`` — percent (``-1`` = indeterminate) + message
    - ``on_finished_ok()`` — update applied, no locked files
    - ``on_relay_needed(str)`` — path to the Windows locked-file relay script
    - ``on_failed(str)`` — install failed
    """

    def __init__(self, release: ReleaseInfo, *,
                 on_progress=None, on_finished_ok=None,
                 on_relay_needed=None, on_failed=None):
        # NON-daemon: run() rewrites the install tree in place
        # (copytree dirs_exist_ok) and runs pip; a daemon thread killed at
        # interpreter exit mid-apply would leave the package half-updated.
        # As a non-daemon thread the process stays alive until the install
        # finishes (it ends in a restart/relay handoff anyway). The checker
        # and fw-downloader stay daemon — their work is interruptible.
        super().__init__(daemon=False)
        self.release = release
        self._on_progress = on_progress
        self._on_finished_ok = on_finished_ok
        self._on_relay_needed = on_relay_needed
        self._on_failed = on_failed

    def run(self):
        try:
            install_root = get_install_root()
        except NotWritableError as e:
            _fire(self._on_failed, f"Install dir not writable: {e}")
            return

        # Use mkdtemp (not TemporaryDirectory context manager) so that on Windows
        # we can leave the directory alive for the relay script to consume.
        tmp_dir = Path(tempfile.mkdtemp(prefix="polyhost-update-"))
        try:
            _fire(self._on_progress, 0, "Starting download...")
            extracted = download_and_extract(
                self.release.tarball_url, tmp_dir,
                progress_cb=lambda pct: _fire(self._on_progress, pct, f"Downloading v{self.release.version}..."),
            )
            _fire(self._on_progress, -1, "Applying update...")
            locked = apply_update(
                extracted, install_root,
                line_cb=lambda line: _fire(self._on_progress, -1, line),
            )
        except Exception as e:  # noqa: BLE001
            log.exception("Update install failed")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            _fire(self._on_failed, str(e))
            return

        try:
            if locked:
                relay_path = _write_relay_script(locked, tmp_dir)
                log.info("Relay script written for %d locked file(s): %s", len(locked), relay_path)
                # Do NOT clean up tmp_dir — relay script needs the source files and
                # will delete the directory itself after copying them.
                _fire(self._on_relay_needed, str(relay_path))
            else:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                _fire(self._on_finished_ok)
        except Exception as e:  # noqa: BLE001
            log.exception("Preparing relay install failed")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            _fire(self._on_failed, str(e))


class FwUpDownloader(threading.Thread):
    """Download a firmware .bin from a GitHub release asset URL to a temp file.

    Callbacks fire on this thread; they mirror the previous Qt signals:

    - ``on_progress(int, str)`` — percent + message
    - ``on_finished(bool, str, str)`` — (ok, error_or_empty, bin_path_or_empty)
    """

    def __init__(self, release: FwUpReleaseInfo, *,
                 on_progress=None, on_finished=None):
        super().__init__(daemon=True)
        self.release = release
        self._on_progress = on_progress
        self._on_finished = on_finished

    def run(self):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="polykybd-fw-", suffix=".bin", delete=False
            ) as tmp:
                tmp_path = tmp.name
                _fire(self._on_progress, 0, "Connecting…")
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
                            _fire(self._on_progress, pct, f"Downloading firmware… {written // 1024} / {total // 1024} KB")
                        else:
                            _fire(self._on_progress, 0, f"Downloading firmware… {written // 1024} KB")
        except Exception as e:  # noqa: BLE001
            log.exception("Firmware download failed")
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            _fire(self._on_finished, False, str(e), "")
            return
        _fire(self._on_finished, True, "", tmp_path)
