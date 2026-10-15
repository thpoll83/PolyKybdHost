"""The UI Automation harvest, run in a helper process (Windows).

`python -m polyhost.services.shortcut_source.worker` reads one JSON request per
line on stdin and answers one JSON line on stdout:

    request   {"id": 3, "app": "chrome", "pid": 1234, "hwnd": 198342}
    answer    {"id": 3, "shortcuts": [{...Shortcut fields...}], "elements": 81234,
               "seconds": 63.2, "why": null, "retry": false, "hwnd": 198342,
               "root_pid": 1234, "root_class": "Chrome_WidgetWin_1"}

It exits when stdin closes, so a dead parent never leaves it behind.

Its stderr is forwarded into the host's log line by line, so a traceback or a
`faulthandler` dump from here is in the next log bundle; it writes nothing else
there.

Why a process and not the harvest thread it used to run on: see
`shortcut_source.out_of_process`.
"""

from __future__ import annotations

import dataclasses
import faulthandler
import json
import sys
import time
import traceback


def answer(request: dict) -> dict:
    """Run one harvest and describe it. Never raises."""
    from polyhost.services.shortcut_source import uia
    reason: dict = {}
    started = time.monotonic()
    try:
        found = uia.shortcuts_for_app(str(request.get("app") or ""),
                                      reason=reason, pid=request.get("pid"),
                                      hwnd=request.get("hwnd"))
    except Exception as exc:  # the backend's own guard should catch this
        found = []
        reason["why"] = f"the UIA harvest raised: {type(exc).__name__}: {exc}"
        traceback.print_exc(file=sys.stderr)
    return {
        "id": request.get("id"),
        "shortcuts": [dataclasses.asdict(sc) for sc in found],
        "elements": reason.get("elements"),
        "seconds": round(time.monotonic() - started, 3),
        "why": reason.get("why"),
        "retry": bool(reason.get("retry")),
        "hwnd": request.get("hwnd"),
        "root_pid": reason.get("root_pid"),
        "root_class": reason.get("root_class"),
    }


def main(stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    try:
        # A native fault in UIA/COM then leaves a stack in the host's log
        # (stderr is forwarded) instead of a helper that silently vanished.
        faulthandler.enable(file=sys.stderr)
    except Exception:
        pass
    try:
        for line in iter(stdin.readline, b""):
            try:
                request = json.loads(line)
            except ValueError:
                print(f"unreadable request ignored: {line[:80]!r}", file=sys.stderr)
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
