"""Pre-flight dependency installer.

Runs from `polyhost/__main__.py` before any heavy imports. If the active
interpreter is missing packages declared in `requirements.txt` (because the
user just updated the source tree manually or because an in-app update only
applied partially), install them so the GUI doesn't crash on launch with an
ImportError.

Uses only the standard library so it can run before the project's
dependencies are present.
"""
import importlib.metadata
import logging
import os
import re
import subprocess
import sys

log = logging.getLogger(__name__)


def missing_requirements(req_file: str) -> list:
    """Return pip-install names from `req_file` that aren't installed.

    Parses comments, blank lines, version specifiers, extras, and environment
    markers conservatively. Returns an empty list when the file is missing.
    """
    if not os.path.isfile(req_file):
        return []
    missing = []
    with open(req_file) as fh:
        for raw in fh:
            line = raw.split("#", 1)[0].strip()
            if not line or line.startswith("-"):
                continue
            name = re.split(r"[<>=!~;\[ ]", line, maxsplit=1)[0].strip()
            if not name:
                continue
            try:
                importlib.metadata.distribution(name)
            except importlib.metadata.PackageNotFoundError:
                missing.append(name)
    return missing


def bootstrap_dependencies(project_root: str) -> None:
    """Install `requirements.txt` from `project_root` if anything is missing."""
    req_file = os.path.join(project_root, "requirements.txt")
    missing = missing_requirements(req_file)
    if not missing:
        return
    print(f"PolyKybdHost bootstrap: missing packages {missing}, "
          f"running pip install -r {req_file}", flush=True)
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", req_file],
            check=False, timeout=300,
        )
    except (subprocess.SubprocessError, OSError) as e:
        log.warning("Bootstrap pip install failed: %s", e)
