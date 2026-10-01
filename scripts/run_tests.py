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

⚠️ Do not run two `xvfb-run -a` invocations at once — see CLAUDE.md; they race
for a display number and the loser hangs. That is separate from the stall above.
"""
from __future__ import annotations

import argparse
import faulthandler
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


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
    ap.add_argument("--timeout", type=float, default=120.0,
                    help="seconds ONE test may run before all thread stacks are "
                         "dumped and the run exits (0 disables the watchdog)")
    args = ap.parse_args()

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
