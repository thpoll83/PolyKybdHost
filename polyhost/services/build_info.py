"""Which host build is running: a release the updater installed, or a git checkout.

The version number alone does not identify a build. Every commit between two
releases carries the same ``__version__``, and the maintainer runs many branch
builds, so a log that says "1.16.0" cannot say which code wrote it. This module
answers the question once per process, for the startup log and the bundle's
diagnostics.txt.

There are two sources, and the order matters:

- The in-app updater copies a release tarball OVER the install tree and leaves
  ``.git`` alone (``updater.EXCLUDES``). The installer clones the repo, so most
  installs have a ``.git`` whose HEAD is OLDER than the files after the first
  update. Reading git there would name a commit that is not running. So the
  updater writes :data:`MARKER_NAME` after a successful apply, with the git
  HEAD it found. The marker wins while its version still matches
  ``__version__`` and HEAD is still that commit: any ``git pull`` or checkout
  after the update makes git the source again, whatever its commit date.
- Otherwise a ``.git`` checkout names the branch and commit, with ``*`` when the
  tracked files differ from HEAD, like the firmware's banner.

Qt-free and never raises: a build-info failure must not break a launch.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

MARKER_NAME = ".polyhost-release.json"
GIT_TIMEOUT_S = 3.0


def install_root() -> Path:
    """The directory holding the ``polyhost`` package (the updater's target)."""
    import polyhost
    return Path(polyhost.__file__).resolve().parent.parent


def write_release_marker(root: Path, tag: str, version: str,
                         published_at: str = "", name: str = "") -> None:
    """Record the release the updater just applied. Logged, never raised."""
    git = _git_state(Path(root))
    data = {
        "tag": tag,
        "version": version,
        "published_at": published_at or "",
        "name": name or "",
        "installed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head": (git or {}).get("head", ""),
    }
    try:
        (Path(root) / MARKER_NAME).write_text(json.dumps(data, indent=2) + "\n",
                                              encoding="utf-8")
    except OSError as e:
        log.warning("Could not write the release marker in %s: %s", root, e)


def _read_marker(root: Path) -> Optional[dict]:
    try:
        data = json.loads((root / MARKER_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _git(root: Path, *args: str) -> Optional[str]:
    kwargs = {}
    if sys.platform == "win32":
        # A console window would flash for each call under pythonw.
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    # Audit: a fixed "git" argv with fixed subcommands and the install root
    # derived from polyhost.__file__; no shell, no external input.
    try:
        out = subprocess.run(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
            ["git", "-C", str(root), *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT_S, **kwargs)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def _git_state(root: Path) -> Optional[dict]:
    """Branch, short hash, commit time and dirty flag of the checkout at ``root``."""
    if not (root / ".git").exists():
        return None
    head = _git(root, "log", "-1", "--abbrev=10", "--format=%h%x00%H%x00%ct%x00%D")
    if not head:
        return {"error": "git unavailable or not a repository"}
    sha, full, ctime, refs = (head.strip().split("\x00") + ["", "", "", ""])[:4]
    branch = "detached"
    for ref in refs.split(", "):
        if ref.startswith("HEAD -> "):
            branch = ref[len("HEAD -> "):]
            break
    status = _git(root, "status", "--porcelain", "--untracked-files=no")
    try:
        committed = datetime.fromtimestamp(int(ctime), timezone.utc)
    except ValueError:
        committed = None
    return {"branch": branch, "sha": sha, "head": full, "committed": committed,
            "dirty": bool(status and status.strip()),
            "dirty_known": status is not None}


def _parse_time(text: str) -> Optional[datetime]:
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _date(text: str) -> str:
    when = _parse_time(text)
    return when.strftime("%Y-%m-%d") if when else "?"


_cached: Optional[str] = None


def describe(root: Optional[Path] = None, version: Optional[str] = None) -> str:
    """One line naming the running build, e.g. ``release v1.16.0 (published …)``.

    The default call is computed once per process and then cached: the code that
    is running does not change after start, and the report dialog asks for this
    on the GUI thread, where a slow git must not cost it seconds."""
    global _cached
    if root is None and version is None:
        if _cached is None:
            _cached = _describe(None, None)
        return _cached
    return _describe(root, version)


def _describe(root: Optional[Path], version: Optional[str]) -> str:
    try:
        from polyhost._version import __version__
        version = version or __version__
        root = Path(root) if root is not None else install_root()
        marker = _read_marker(root)
        git = _git_state(root)
        if marker and marker.get("version") == version:
            if marker.get("git_head", "") == (git or {}).get("head", ""):
                text = (f"release {marker.get('tag') or 'v' + version}, published "
                        f"{_date(marker.get('published_at', ''))}, installed by update "
                        f"{_date(marker.get('installed_at', ''))}")
                if git and "sha" in git:
                    text += f" (git {git['branch']}@{git['sha']} predates the files)"
                return text
        if git and "sha" in git:
            flag = "*" if git["dirty"] else ("" if git["dirty_known"] else "?")
            when = git["committed"].strftime("%Y-%m-%d") if git["committed"] else "?"
            return f"git {git['branch']}@{git['sha']}{flag} {when}"
        if git:
            return f"git checkout, {git['error']}"
        return "unknown source (no git checkout, no update marker)"
    except Exception as e:  # noqa: BLE001 - diagnostics must never break a launch
        return f"unknown ({type(e).__name__}: {e})"


def banner(root: Optional[Path] = None) -> str:
    """The startup banner line, shaped like the firmware's ``== … ==`` banner."""
    from polyhost._version import __protocol__, __version__
    return (f"== PolyKybdHost {__version__} P{__protocol__} | "
            f"build {describe(root, __version__)} ==")
