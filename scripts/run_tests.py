#!/usr/bin/env python3
"""Run the unit suite with a stall watchdog.

The suite is ~25 s (about 27 s under xvfb, where the GUI-subprocess tests
actually run instead of skipping). Twice, on 2026-08-03, it instead wedged past a
200 s timeout with no output — and a bare `timeout` kill tells you *nothing*
about where. This runner arms `faulthandler.dump_traceback_later`, so a stall
prints every thread's stack and exits non-zero rather than dying silently.

    python scripts/run_tests.py                 # whole suite, 180 s watchdog
    python scripts/run_tests.py --timeout 60
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-s", "--start-dir", default="./tests",
                    help="discovery root (default: ./tests)")
    ap.add_argument("-p", "--pattern", default="*_test.py")
    ap.add_argument("-v", "--verbose", action="count", default=1)
    ap.add_argument("--timeout", type=float, default=180.0,
                    help="seconds before dumping all thread stacks and exiting "
                         "(0 disables the watchdog)")
    args = ap.parse_args()

    faulthandler.enable()
    if args.timeout > 0:
        # exit=True so a wedged run fails the command instead of hanging forever.
        # The dump names the blocking call in EVERY thread, which is what a plain
        # `timeout` kill throws away.
        faulthandler.dump_traceback_later(args.timeout, exit=True)

    suite = unittest.TestLoader().discover(
        args.start_dir, pattern=args.pattern, top_level_dir=str(REPO_ROOT))
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=args.verbose).run(suite)
    if args.timeout > 0:
        faulthandler.cancel_dump_traceback_later()

    print(f"\nelapsed {time.monotonic() - started:.1f}s "
          f"(expect ~25s; ~27s under xvfb)")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
