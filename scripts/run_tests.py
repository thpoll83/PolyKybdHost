#!/usr/bin/env python3
"""Run the unit suite with a stall watchdog.

Twice, on 2026-08-03, the suite wedged past a 200 s timeout with no output —
and a bare `timeout` kill tells you *nothing* about where. This runner arms
`faulthandler.dump_traceback_later`, so a stall prints every thread's stack and
exits non-zero rather than dying silently.

The watchdog is re-armed at the START OF EACH TEST, so `--timeout` bounds one
test (plus the class/module fixtures around it), never the whole run. A
whole-run budget went stale as the suite grew: it was documented as ~25 s, then
65–90 s, then measured 125–131 s, and a budget below the real length fires on a
healthy run, landing its dump wherever teardown happens to be.

    python scripts/run_tests.py                 # whole suite, 120 s per test
    python scripts/run_tests.py --timeout 30
    python scripts/run_tests.py -s tests/device # one package
    xvfb-run -a python scripts/run_tests.py     # + the GUI-subprocess tests

Use it in place of `python -m unittest discover …` whenever a run might hang;
`-m unittest` remains perfectly fine for a quick targeted module.

Before it runs anything it checks `requirements-test.txt`. In a venv it installs
what is missing (`--no-install` only reports); outside one it stops with the
command, so it never installs into a system Python. A missing package used to
make dozens of tests ERROR as if they were regressions, in every fresh container.

⚠️ Do not run two `xvfb-run -a` invocations at once — see CLAUDE.md; they race
for a display number and the loser hangs. That is separate from the stall above.
"""
from __future__ import annotations

import argparse
import faulthandler
import importlib
import os
import re
import shutil
import subprocess
import sys
import time
import unittest
from importlib import metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_REQUIREMENTS = REPO_ROOT / "requirements-test.txt"


def requirement_lines(path: Path, _seen=None) -> list[str]:
    """The requirement lines of ``path``, following ``-r`` includes."""
    seen = set() if _seen is None else _seen
    path = path.resolve()
    if path in seen:
        return []
    seen.add(path)
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split(" #", 1)[0].split("\t#", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r "):
            lines += requirement_lines(path.parent / line[3:].strip(), seen)
        else:
            lines.append(line)
    return lines


def missing_requirements(path: Path = TEST_REQUIREMENTS) -> list[str]:
    """The lines of ``path`` this interpreter does not satisfy.

    Uses ``packaging`` for markers and versions when it is installed. A venv
    without it (``packaging`` is itself on the list) gets a name-only check and
    the one marker form the lists use, ``sys_platform == "…"``."""
    try:
        from packaging.requirements import Requirement
    except ImportError:
        Requirement = None
    missing = []
    for line in requirement_lines(path):
        if Requirement is not None:
            req = Requirement(line)
            if req.marker is not None and not req.marker.evaluate():
                continue
            name, spec = req.name, req.specifier
        else:
            m = re.search(r';\s*sys_platform\s*==\s*["\']([^"\']+)["\']', line)
            if m and m.group(1) != sys.platform:
                continue
            name, spec = re.match(r"[A-Za-z0-9._-]+", line).group(0), None
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            missing.append(line)
            continue
        if spec and not spec.contains(version, prereleases=True):
            missing.append(line)
    return list(dict.fromkeys(missing))   # both lists name Pillow and fonttools


def check_requirements(install: bool) -> bool:
    """True when the test requirements are met, installing them first when
    ``install`` and this is a venv. Prints what it found and did."""
    missing = missing_requirements()
    if not missing:
        return True
    command = [sys.executable, "-m", "pip", "install", "-r", str(TEST_REQUIREMENTS)]
    print("Missing test requirements: " + ", ".join(missing), flush=True)
    in_venv = sys.prefix != sys.base_prefix
    if not (install and in_venv):
        why = "--no-install" if in_venv else "not a venv (use .venv/bin/python)"
        print(f"Not installing ({why}). Install with:\n  {' '.join(command)}")
        return False
    print("Installing: " + " ".join(command), flush=True)
    if subprocess.run(command, check=False).returncode != 0:
        return False
    still = missing_requirements()
    if still:
        print("Still missing after the install: " + ", ".join(still))
    return not still


def check_system() -> None:
    """Warn about the system pieces pip cannot install."""
    try:
        # import_module, not `import hid`: the import loads the hidapi library,
        # and an unused name is a CodeQL finding that noqa does not silence.
        importlib.import_module("hid")
    except ImportError as exc:
        print(f"WARNING: the hid module does not load ({exc}). Install the hidapi "
              "system libraries: sudo apt-get install -y libhidapi-hidraw0 libhidapi-libusb0")
    # pywinctl imports pymonctl, which on Linux needs xrandr and xset: without
    # them every test that imports handler/active_window ERRORs (74 of them on
    # 2026-10-22, the same on main).
    if sys.platform.startswith("linux") and not (shutil.which("xrandr") and shutil.which("xset")):
        print("WARNING: xrandr or xset is missing, so pywinctl does not import and the "
              "window tests ERROR: sudo apt-get install -y x11-xserver-utils")
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        print("NOTE: no DISPLAY, so the GUI tests skip. Run under `xvfb-run -a` for them.")


class _WatchdogResult(unittest.TextTestResult):
    """Re-arms the stall watchdog as each test starts."""
    timeout = 0.0

    def startTest(self, test):
        if self.timeout > 0:
            faulthandler.dump_traceback_later(self.timeout, exit=True)
        super().startTest(test)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-s", "--start-dir", default="./tests",
                    help="discovery root (default: ./tests)")
    ap.add_argument("-p", "--pattern", default="*_test.py")
    ap.add_argument("-v", "--verbose", action="count", default=1)
    ap.add_argument("--no-install", action="store_true",
                    help="only report missing test requirements, do not install them")
    ap.add_argument("--timeout", type=float, default=120.0,
                    help="seconds ONE test may run before all thread stacks are "
                         "dumped and the run exits (0 disables the watchdog)")
    args = ap.parse_args()

    if not check_requirements(install=not args.no_install):
        return 2
    check_system()

    faulthandler.enable()
    if args.timeout > 0:
        # exit=True so a wedged run fails the command instead of hanging forever.
        # The dump names the blocking call in EVERY thread, which is what a plain
        # `timeout` kill throws away.
        # The first window covers discovery (the imports); each test re-arms it.
        faulthandler.dump_traceback_later(args.timeout, exit=True)
    _WatchdogResult.timeout = args.timeout

    suite = unittest.TestLoader().discover(
        args.start_dir, pattern=args.pattern, top_level_dir=str(REPO_ROOT))
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=args.verbose,
                                     resultclass=_WatchdogResult).run(suite)
    if args.timeout > 0:
        faulthandler.cancel_dump_traceback_later()

    print(f"\nelapsed {time.monotonic() - started:.1f}s")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
