"""Agents on a forwarder's machine (a second computer without the keyboard).

Reports: the agent's hook runs `polyctl agents hook <vendor> --host <keyboard PC>`,
which sends `agents.report` over the authenticated window-report endpoint
(server/window_report_server.py). `sanitize_report()` bounds every field there,
because that endpoint is reachable from the network.

Raises: the keyboard host cannot open a connection to the forwarder, so a raise
for a remote agent waits in `RemoteRaiseQueue` and leaves with the reply to that
forwarder's next `window.report` (PolyCore.report_window). The forwarder's
`RemoteRaiseFollower` turns a new sequence number into one local raise. While a
machine has agents on the keys, the reply also asks its forwarder for a 1 s
heartbeat, so a press reaches it within about a second instead of 15.

⚠️ HOST-5 (polykybd-ctnd docs/SECURITY_AUDIT.md): messages on this connection are
authenticated at the handshake only. A forged reply can make the forwarder raise
one of ITS windows; it cannot type, read, or choose an arbitrary program.
"""
from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass

MAX_TEXT = {"vendor": 32, "session_id": 160, "event": 24, "headline": 80,
            "cwd": 400, "machine": 64, "window": 64, "surface": 16}
STATES = ("working", "waiting", "done", "idle", "stale", "ended")


def sanitize_report(params) -> dict | None:
    """The fields of a network `agents.report`, bounded, or None when unusable."""
    if not isinstance(params, dict):
        return None
    out = {}
    for name, limit in MAX_TEXT.items():
        value = params.get(name)
        if value is None:
            continue
        if not isinstance(value, (str, int)):
            return None
        out[name] = str(value)[:limit]
    state = params.get("state")
    if state is not None:
        if not isinstance(state, str) or state.lower() not in STATES:
            return None
        out["state"] = state.lower()
    pid = params.get("pid")
    if isinstance(pid, int) and not isinstance(pid, bool) and 0 < pid < 1 << 31:
        out["pid"] = pid
    if not out.get("vendor") or not out.get("session_id"):
        return None
    out["machine"] = out.get("machine") or "remote"
    return out


def agent_payload(agent) -> dict:
    """What the forwarder needs to find the agent's window on its machine."""
    return {"vendor": agent.vendor, "session_id": agent.session_id, "pid": agent.pid,
            "cwd": agent.cwd, "window": agent.window, "headline": agent.display_headline}


class RemoteRaiseQueue:
    """Host side: the newest raise per forwarder machine."""

    def __init__(self):
        self._lock = threading.Lock()
        self._seq = itertools.count(1)
        self._pending: dict[str, dict] = {}

    def request(self, agent) -> int:
        with self._lock:
            seq = next(self._seq)
            self._pending[agent.machine] = {"seq": seq, "agent": agent_payload(agent)}
            return seq

    def for_machine(self, machine: str) -> dict | None:
        """The newest raise for `machine`. Not removed: the forwarder dedupes by
        seq, so a reply that is lost on the way does not lose the raise."""
        with self._lock:
            return self._pending.get(machine or "")


class RemoteRaiseFollower:
    """Forwarder side: turns a reply's `agent_raise` into at most one raise per seq.
    The first reply only sets the baseline, so a raise queued before this forwarder
    started (or reconnected) is not replayed."""

    def __init__(self):
        self._last = None

    def follow(self, reply) -> dict | None:
        raise_ = (reply or {}).get("agent_raise") if isinstance(reply, dict) else None
        seq = raise_.get("seq") if isinstance(raise_, dict) else None
        if not isinstance(seq, int):
            if self._last is None:
                self._last = 0
            return None
        if self._last is None or seq <= self._last:
            self._last = seq if self._last is None else max(self._last, seq)
            return None
        self._last = seq
        agent = raise_.get("agent")
        return agent if isinstance(agent, dict) else None


@dataclass
class RemoteAgent:
    """Enough of an Agent for raiser.raise_agent on the forwarder's machine."""
    vendor: str = ""
    session_id: str = ""
    pid: int = 0
    cwd: str = ""
    window: str = ""
    display_headline: str = ""

    @classmethod
    def from_payload(cls, payload: dict) -> "RemoteAgent":
        return cls(vendor=str(payload.get("vendor", "")),
                   session_id=str(payload.get("session_id", "")),
                   pid=int(payload.get("pid") or 0), cwd=str(payload.get("cwd", "")),
                   window=str(payload.get("window", "")),
                   display_headline=str(payload.get("headline", "")))
