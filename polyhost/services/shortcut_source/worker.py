"""The UI Automation harvest, run in a helper process (Windows).

`python -m polyhost.services.shortcut_source.worker` reads one JSON request per
line on stdin and answers one JSON line on stdout:

    request   {"id": 3, "app": "chrome", "pid": 1234}
    answer    {"id": 3, "shortcuts": [{...Shortcut fields...}], "elements": 81234,
               "seconds": 63.2, "why": null}

It exits when stdin closes, so a dead parent never leaves it behind.

Why a process and not the harvest thread it used to run on: see
`shortcut_source.out_of_process`.
"""

from __future__ import annotations

import dataclasses
import json
import sys
import time


def answer(request: dict) -> dict:
    """Run one harvest and describe it. Never raises."""
    from polyhost.services.shortcut_source import uia
    reason: dict = {}
    started = time.monotonic()
    try:
        found = uia.shortcuts_for_app(str(request.get("app") or ""),
                                      reason=reason, pid=request.get("pid"))
    except Exception as exc:  # the backend's own guard should catch this
        found = []
        reason["why"] = f"the UIA harvest raised: {type(exc).__name__}: {exc}"
    return {
        "id": request.get("id"),
        "shortcuts": [dataclasses.asdict(sc) for sc in found],
        "elements": reason.get("elements"),
        "seconds": round(time.monotonic() - started, 3),
        "why": reason.get("why"),
    }


def main(stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    try:
        for line in iter(stdin.readline, b""):
            try:
                request = json.loads(line)
            except ValueError:
                continue
            if not isinstance(request, dict):
                continue
            stdout.write(json.dumps(answer(request)).encode("utf-8") + b"\n")
            stdout.flush()
    finally:
        from polyhost.services.shortcut_source import uia
        uia.release_thread()
    return 0


if __name__ == "__main__":
    sys.exit(main())
