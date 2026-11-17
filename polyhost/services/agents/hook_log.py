"""The agent hook log: one line for each run of `polyctl agents hook <vendor>`.

A hook must exit 0 and print nothing (polyctl._agents_hook_main), so a hook that
reaches no host fails without a trace. This file is that trace: what the hook
read, where it sent the report, and how it ended. `polyctl agents hooks check`
prints its last lines.

    [2026-11-17 09:12:03,412] claude-code PostToolUse working 3f2a9c1e -> local: ok (84 ms)
    [2026-11-17 09:12:07,950] codex agent-turn-complete done 019a77b2 -> desktop:50163: timeout in connect (4000 ms)

⚠️ No prompt text, tool arguments, titles or file contents: the event name, the
state, the first 8 characters of the session id and the target only.

The file is in the config folder, next to the host's own files: a hook runs in the
agent's working folder, where the host's relative log names do not point. It is
moved to `<name>.1` when it passes MAX_BYTES. Writing never raises.
"""
from __future__ import annotations

import os
import time

FILE_NAME = "agent_hooks.log"
MAX_BYTES = 256 * 1024          # about 2500 lines; then one older file is kept
SESSION_CHARS = 8
_FIELD_CHARS = 60               # an event or target name longer than this is cut


def default_path() -> str:
    from polyhost.server import protocol
    return protocol.agent_hook_log_path()


def _clean(text, limit=_FIELD_CHARS) -> str:
    """One field: no line breaks, at most `limit` characters, '-' when empty."""
    text = " ".join(str(text or "").split())
    return text[:limit] or "-"


def format_line(vendor, event, state, session, target, result, ms, now=None) -> str:
    now = time.time() if now is None else now
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
    return (f"[{stamp},{int(now * 1000) % 1000:03d}] {_clean(vendor)} {_clean(event)} "
            f"{_clean(state)} {_clean(session, SESSION_CHARS)} -> {_clean(target)}: "
            f"{_clean(result, 200)} ({int(ms)} ms)")


def write(vendor, event, state, session, target, result, ms, path=None) -> None:
    """Append one line. Never raises: the hook goes on without its log."""
    try:
        path = path or default_path()
        try:
            if os.path.getsize(path) > MAX_BYTES:
                os.replace(path, path + ".1")
        except OSError:
            pass    # no file yet, or another hook moved it first
        line = format_line(vendor, event, state, session, target, result, ms)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001 - see the docstring
        pass


def tail(lines: int = 10, vendor: str | None = None, path=None) -> list[str]:
    """The last `lines` lines, of one vendor when given, oldest first."""
    path = path or default_path()
    out = []
    for name in (path + ".1", path):
        try:
            with open(name, encoding="utf-8", errors="replace") as fh:
                out.extend(line.rstrip("\n") for line in fh)
        except OSError:
            continue    # that file does not exist (yet)
    if vendor:
        out = [line for line in out if line.split("] ", 1)[-1].startswith(vendor + " ")]
    return out[-lines:] if lines > 0 else []
