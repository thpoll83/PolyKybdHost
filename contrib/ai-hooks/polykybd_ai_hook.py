#!/usr/bin/env python3
"""Map an AI agent's lifecycle events onto the PolyKybd AI key.

ONE script for every agent, because the only thing an integration has to do is run a
command when something happens — which is a feature Claude Code, Codex and most
others already have. It reads the event however that tool delivers it, decides a
state, and calls `polyctl ai state <state>`.

Claude Code (hooks; the event JSON arrives on stdin, the event name in the JSON and
in $CLAUDE_HOOK_EVENT). In ~/.claude/settings.json:

    {
      "hooks": {
        "UserPromptSubmit": [{"hooks": [{"type": "command",
           "command": "python3 /path/to/polykybd_ai_hook.py"}]}],
        "Notification":     [{"hooks": [{"type": "command",
           "command": "python3 /path/to/polykybd_ai_hook.py"}]}],
        "Stop":             [{"hooks": [{"type": "command",
           "command": "python3 /path/to/polykybd_ai_hook.py"}]}]
      }
    }

OpenAI Codex CLI (the `notify` program; the event JSON is the LAST argv argument, and
there is exactly one event — agent-turn-complete). In ~/.codex/config.toml:

    notify = ["python3", "/path/to/polykybd_ai_hook.py"]

Anything else: call it with a state directly, which is also how you test it —

    python3 polykybd_ai_hook.py working

⚠️ It NEVER fails the tool it is hooked into. A hook that exits non-zero can block the
agent, and a keyboard light is not worth that: every failure path prints to stderr and
exits 0.
"""
import json
import os
import shutil
import subprocess
import sys

# What each event means for the light. The keys are matched case-insensitively
# against the event name the tool reports, so a tool that spells its events
# differently only needs a line here.
EVENT_STATE = {
    # Claude Code
    "userpromptsubmit": "working",
    "pretooluse": "working",
    "posttooluse": "working",
    "notification": "attention",      # "Claude needs your permission…"
    "stop": "idle",                   # the turn finished
    "subagentstop": "working",        # a subagent finished; the main turn goes on
    "sessionstart": "idle",
    "sessionend": "off",
    # Codex CLI (`notify`)
    "agent-turn-complete": "idle",
}


def _warn(msg):
    print(f"polykybd-ai-hook: {msg}", file=sys.stderr)


def read_event():
    """The event payload, however this tool delivers it: a literal state as argv, a
    Codex JSON blob as the last argv argument, or a Claude Code JSON object on stdin."""
    for arg in sys.argv[1:]:
        if arg.strip().startswith("{"):
            try:
                return json.loads(arg)
            except json.JSONDecodeError:
                pass
    if len(sys.argv) > 1:
        return {"state": sys.argv[1]}
    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"state": raw}
    return {}


def decide_state(event):
    """Which state this event means, or None to do nothing.

    An explicit `state` always wins, so a tool with no hooks can drive the light with
    one plain command. Otherwise the event NAME decides — from the payload, or from
    the environment variable Claude Code sets."""
    explicit = event.get("state")
    if explicit:
        return str(explicit)
    name = (event.get("hook_event_name") or event.get("type")
            or os.environ.get("CLAUDE_HOOK_EVENT") or "")
    return EVENT_STATE.get(str(name).strip().lower())


def polyctl():
    """The polyctl to run: $POLYCTL, one on PATH, or this checkout's own module."""
    override = os.environ.get("POLYCTL")
    if override:
        return [override]
    found = shutil.which("polyctl")
    if found:
        return [found]
    return [sys.executable, "-m", "polyhost.cli.polyctl"]


def main():
    event = read_event()
    state = decide_state(event)
    if not state:
        return 0   # an event we have no opinion about is not an error
    cmd = polyctl() + ["ai", "state", state]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except FileNotFoundError:
        _warn("polyctl not found — set $POLYCTL or put it on PATH")
        return 0
    except subprocess.TimeoutExpired:
        _warn("polyctl timed out (is the PolyKybd host running?)")
        return 0
    if res.returncode != 0:
        _warn((res.stderr or res.stdout or "polyctl failed").strip())
    return 0


if __name__ == "__main__":
    # Never fail the agent over a keyboard light.
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        _warn(f"unexpected error: {exc}")
        sys.exit(0)
