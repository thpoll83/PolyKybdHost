import os
import sys
import time

_t_process = time.monotonic()   # ~interpreter start (os/sys/time already loaded)

current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))

if __name__ == "__main__" and parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    print("Script is executed directly, sys.path corrected to:\n", sys.path)

# Hard requirement: Python 3.10+. The codebase uses `match` statements
# (polyhost/device/poly_kybd.py) and PEP 604 `X | Y` annotations evaluated at
# import time, both of which raise on 3.9 — most visibly the macOS system
# interpreter from the Xcode Command Line Tools (/Library/Developer/...python3,
# which is 3.9). Without this guard the user just sees a cryptic
# "TypeError: unsupported operand type(s) for |" deep in an import. Fail early
# and tell them what to do instead. This block is stdlib-only and 3.9-parseable,
# so it always runs before any 3.10-only module is imported.
if sys.version_info < (3, 10):
    _v = ".".join(str(n) for n in sys.version_info[:3])
    sys.stderr.write(
        "PolyKybdHost requires Python 3.10 or newer, but this interpreter is "
        f"Python {_v}\n  ({sys.executable}).\n\n"
        "On macOS the system 'python3' from the Xcode Command Line Tools is 3.9 "
        "and will not work.\nInstall a newer Python (e.g. 'brew install python' "
        "or python.org) and create the\nvirtual environment with it, for example:\n\n"
        "    python3.12 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt\n"
        "    .venv/bin/python -m polyhost\n"
    )
    raise SystemExit(1)

from polyhost._bootstrap import bootstrap_dependencies

bootstrap_dependencies(parent_dir)
_t_bootstrap = time.monotonic()

from polyhost.main_app import main

# Pass the early timestamps so main() can log how long bootstrap + the
# pre-logging imports took — to tell apart "our startup is slow" from
# "Windows took its time firing the task / cold-starting the interpreter".
main(launch_monotonic=_t_process, post_bootstrap_monotonic=_t_bootstrap)

