"""Pre-flight dependency installer.

Runs from `polyhost/__main__.py` before any heavy imports. If the active
interpreter is missing packages declared in `requirements.txt` (because the
user just updated the source tree manually or because an in-app update only
applied partially), install them so the GUI doesn't crash on launch with an
ImportError.

Uses only the standard library so it can run before the project's
dependencies are present.

importlib.metadata / re / subprocess are imported lazily inside the functions
that need them: importing importlib.metadata cold-pulls a heavy stdlib chain
(~3s on Windows under antivirus), and on the common path — requirements.txt
unchanged, scan skipped via the marker — we must not pay that just to read a
one-line marker file.
"""
import logging
import os
import sys

log = logging.getLogger(__name__)


def _marker_applies(line: str) -> bool:
    """True if the requirement's environment marker matches this platform.

    A line like ``pywin32; sys_platform == "win32"`` should be ignored on
    Linux/macOS, otherwise it is reported missing on every launch and the
    bootstrap reruns pip needlessly. Falls back to including the line if
    `packaging` isn't importable yet (it gets installed on the first run).
    """
    if ";" not in line:
        return True
    try:
        from packaging.requirements import Requirement
        req = Requirement(line)
        return req.marker is None or req.marker.evaluate()
    except Exception:
        return True


def missing_requirements(req_file: str) -> list:
    """Return pip-install names from `req_file` that aren't installed.

    Parses comments, blank lines, version specifiers, extras, and environment
    markers conservatively. Returns an empty list when the file is missing.
    """
    if not os.path.isfile(req_file):
        return []
    import importlib.metadata
    import re
    missing = []
    with open(req_file) as fh:
        for raw in fh:
            line = raw.split("#", 1)[0].strip()
            if not line or line.startswith("-"):
                continue
            if not _marker_applies(line):
                continue
            name = re.split(r"[<>=!~;\[ ]", line, maxsplit=1)[0].strip()
            if not name:
                continue
            try:
                importlib.metadata.distribution(name)
            except importlib.metadata.PackageNotFoundError:
                missing.append(name)
    return missing


def _deps_marker_path() -> str:
    """Per-interpreter marker recording the requirements.txt signature last
    verified present. Lives in the venv (sys.prefix) — user-writable and
    git-ignored."""
    return os.path.join(sys.prefix, ".polyhost_deps_ok")


def _req_signature(req_file: str):
    """Cheap change-detector for requirements.txt: 'mtime_ns:size' (None if absent).
    Nanosecond mtime so two same-size edits within one second still differ."""
    try:
        st = os.stat(req_file)
    except OSError:
        return None
    return f"{st.st_mtime_ns}:{st.st_size}"


def bootstrap_dependencies(project_root: str) -> None:
    """Install `requirements.txt` from `project_root` if anything is missing.

    The importlib.metadata scan is surprisingly costly on Windows under
    antivirus (~1.3 s, measured on the GUI's startup path), so skip it entirely
    when requirements.txt is unchanged since the last successful check — a normal
    launch then pays nothing. A manual source update that rewrites
    requirements.txt changes its mtime/size and re-triggers the check. (Trade-off:
    manually uninstalling a dep without touching requirements.txt won't be
    re-detected until the file changes — acceptable for a startup safety net.)"""
    req_file = os.path.join(project_root, "requirements.txt")
    if not os.path.isfile(req_file):
        return
    sig = _req_signature(req_file)
    marker = _deps_marker_path()
    if sig is not None:
        try:
            with open(marker, encoding="utf-8") as fh:
                if fh.read().strip() == sig:
                    return  # unchanged since last OK — skip the scan entirely
        except OSError:
            pass

    missing = missing_requirements(req_file)
    if missing:
        # print() is a no-op crash under pythonw (sys.stdout is None), so guard it.
        if sys.stdout is not None:
            print(f"PolyKybdHost bootstrap: missing packages {missing}, "
                  f"running pip install -r {req_file}", flush=True)
        import subprocess
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", req_file],
                check=False, timeout=300,
            )
        except (subprocess.SubprocessError, OSError) as e:
            log.warning("Bootstrap pip install failed: %s", e)
            return  # leave the marker unwritten so the next launch retries
        if proc.returncode != 0:
            return  # install failed — retry next launch, don't record success

    # Everything present (or freshly installed): record the signature so the
    # next launch skips the scan.
    if sig is not None:
        try:
            with open(marker, "w", encoding="utf-8") as fh:
                fh.write(sig)
        except OSError:
            pass
