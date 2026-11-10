"""The agent registry: every agent session the adapters report, with a stable key.

Qt-free and thread-safe: hooks report through the control socket (server threads),
the title scanner from its own thread, the HID worker reads pages.

An agent keeps its key (slot) for as long as it exists, so the user can learn
positions. Slot N is key N % page_size on page N // page_size.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

from polyhost.services.agents.model import ENDED, AgentState, vendor

# ⚠️ Prototype values, not decided yet (docs/agent-registry-plan.md, open questions).
# A WORKING agent with no event for this long is shown as STALE.
STALE_AFTER_S = 30 * 60
# An IDLE or STALE agent with no event for this long is removed and frees its key.
FORGET_AFTER_S = 4 * 60 * 60
# A PreToolUse without a PostToolUse for this long reads as a permission prompt,
# for vendors whose hooks have no event for one (Vendor.infer_waiting).
PENDING_TOOL_WAIT_S = 5.0

PAGE_SIZE = 10


@dataclass
class Agent:
    vendor: str
    session_id: str
    state: AgentState = AgentState.IDLE
    since: float = 0.0
    last_event: float = 0.0
    slot: int = 0
    headline: str = ""
    label: str = ""
    cwd: str = ""
    surface: str = ""
    machine: str = "local"
    pid: int = 0
    window: str = ""            # an opaque window id the raiser understands
    source: str = "hook"        # "hook" or "title"
    pending_tool_since: float = 0.0
    waiting_inferred: bool = False
    extra: dict = field(default_factory=dict)
    # 1, 2, ... when other agents would show the same headline (set by agents()),
    # 0 when this one is unique.
    dup_number: int = 0
    # The registry has seen `pid` alive. Only then does its exit remove the entry:
    # a pid that was never alive (a hook's short-lived shell) proves nothing.
    pid_seen_alive: bool = False

    @property
    def key(self) -> tuple:
        return (self.vendor, self.session_id)

    @property
    def base_headline(self) -> str:
        """The user's label, the session title, the directory, or the vendor."""
        if self.label:
            return self.label
        if self.headline:
            return self.headline
        if self.cwd:
            # Either separator: a forwarder on another OS can report the path.
            path = self.cwd.replace("\\", "/").rstrip("/")
            return path.rsplit("/", 1)[-1] or self.cwd
        return vendor(self.vendor).name

    @property
    def display_headline(self) -> str:
        """What the keycap shows: base_headline, numbered when other agents would
        show the same text (two sessions in one folder: "agent 1", "agent 2")."""
        base = self.base_headline
        return f"{base} {self.dup_number}" if self.dup_number else base

    def to_dict(self) -> dict:
        return {
            "vendor": self.vendor, "session_id": self.session_id,
            "state": self.state.name.lower(), "since": self.since,
            "last_event": self.last_event, "slot": self.slot,
            "page": self.slot // PAGE_SIZE, "key": self.slot % PAGE_SIZE,
            "headline": self.display_headline, "label": self.label, "cwd": self.cwd,
            "surface": self.surface, "machine": self.machine, "pid": self.pid,
            "source": self.source, "waiting_inferred": self.waiting_inferred,
        }


class AgentRegistry:
    def __init__(self, clock=time.monotonic, page_size: int = PAGE_SIZE, is_alive=None):
        """`is_alive(pid)`: when given, tick() removes a hook-reported agent whose
        process has exited (closed terminal, no SessionEnd), once it has seen that
        process alive."""
        self._clock = clock
        self._is_alive = is_alive
        self.page_size = page_size
        self._lock = threading.RLock()
        self._agents: dict[tuple, Agent] = {}
        self._hook_vendors: set[str] = set()   # vendors that reported through a hook
        self.version = 0                       # incremented on every visible change

    # ---- writers ---------------------------------------------------------------

    def report(self, vendor_id: str, session_id: str, state=None, *, event: str = "",
               headline: str | None = None, cwd: str | None = None,
               surface: str | None = None, machine: str | None = None,
               pid: int | None = None, window: str | None = None,
               source: str = "hook") -> dict | None:
        """Create or update one agent. `state` is an AgentState, a state word,
        ENDED (removes the entry) or None (fields only). `event` is the
        normalised hook event, used for the pending-tool inference. Returns the
        agent as a dict, or None when it was removed or refused."""
        vendor_id = (vendor_id or "").strip().lower()
        session_id = str(session_id or "").strip()
        if not vendor_id or not session_id:
            return None
        now = self._clock()
        with self._lock:
            key = (vendor_id, session_id)
            if state == ENDED:
                if self._agents.pop(key, None) is not None:
                    self.version += 1
                return None
            if source == "hook":
                self._hook_vendors.add(vendor_id)
                self._drop_title_entries(vendor_id)
            elif vendor_id in self._hook_vendors:
                # Hooks report this vendor already; a title entry would show the
                # same session twice.
                return None
            agent = self._agents.get(key)
            if agent is None:
                agent = Agent(vendor_id, session_id, since=now, last_event=now,
                              slot=self._free_slot(), source=source)
                self._agents[key] = agent
                self.version += 1
            agent.last_event = now
            before = (agent.state, agent.headline, agent.label)
            if state is not None:
                new_state = AgentState.parse(state)
                if new_state == AgentState.DONE and agent.state == AgentState.IDLE \
                        and (event == "idle_prompt" or source == "title"):
                    # Already seen. Claude Code's idle reminder and a title that
                    # still reads "finished" are repeats, not a new finished turn.
                    new_state = AgentState.IDLE
                if new_state != agent.state:
                    agent.state = new_state
                    agent.since = now
                agent.waiting_inferred = False
            if event == "pretool" and vendor(vendor_id).infer_waiting:
                agent.pending_tool_since = now
            elif event in ("posttool", "stop", "prompt"):
                agent.pending_tool_since = 0.0
            for name, value in (("headline", headline), ("cwd", cwd), ("surface", surface),
                                ("machine", machine), ("window", window)):
                if value:
                    setattr(agent, name, str(value))
            if pid and int(pid) != agent.pid:
                agent.pid = int(pid)
                agent.pid_seen_alive = False
            if (agent.state, agent.headline, agent.label) != before:
                self.version += 1
            return agent.to_dict()

    def label(self, vendor_id: str, session_id: str, text: str) -> bool:
        with self._lock:
            agent = self._agents.get((vendor_id, session_id))
            if agent is None:
                return False
            agent.label = (text or "").strip()
            self.version += 1
            return True

    def forget(self, vendor_id: str, session_id: str) -> bool:
        with self._lock:
            if self._agents.pop((vendor_id, session_id), None) is None:
                return False
            self.version += 1
            return True

    def mark_seen(self, vendor_id: str, session_id: str) -> None:
        """The user looked at the agent: DONE becomes IDLE."""
        with self._lock:
            agent = self._agents.get((vendor_id, session_id))
            if agent is not None and agent.state == AgentState.DONE:
                agent.state = AgentState.IDLE
                agent.since = self._clock()
                self.version += 1

    def drop_missing_titles(self, present_ids: set) -> None:
        """Remove title-scan entries whose window is gone."""
        with self._lock:
            gone = [k for k, a in self._agents.items()
                    if a.source == "title" and a.session_id not in present_ids]
            for k in gone:
                del self._agents[k]
            if gone:
                self.version += 1

    def tick(self) -> None:
        """Time-based transitions: inferred waiting, stale, forget."""
        now = self._clock()
        with self._lock:
            changed = False
            for key, agent in list(self._agents.items()):
                idle_for = now - agent.last_event
                if (agent.pending_tool_since and agent.state == AgentState.WORKING
                        and now - agent.pending_tool_since >= PENDING_TOOL_WAIT_S):
                    agent.state = AgentState.WAITING
                    agent.since = now
                    agent.waiting_inferred = True
                    agent.pending_tool_since = 0.0
                    changed = True
                if agent.state == AgentState.WORKING and idle_for >= STALE_AFTER_S:
                    agent.state = AgentState.STALE
                    agent.since = now
                    changed = True
                if (agent.state in (AgentState.IDLE, AgentState.STALE)
                        and idle_for >= FORGET_AFTER_S):
                    del self._agents[key]
                    changed = True
                    continue
                if (self._is_alive is not None and agent.source == "hook" and agent.pid
                        and agent.machine == "local"):   # a remote pid means nothing here
                    if self._is_alive(agent.pid):
                        agent.pid_seen_alive = True
                    elif agent.pid_seen_alive:
                        del self._agents[key]     # its process exited: closed terminal
                        changed = True
            if changed:
                self.version += 1

    # ---- readers ---------------------------------------------------------------

    def agents(self) -> list[Agent]:
        """Copies of the agents, by key, with dup_number set across all pages."""
        with self._lock:
            out = sorted((Agent(**vars(a)) for a in self._agents.values()),
                         key=lambda a: a.slot)
        groups: dict[str, list[Agent]] = {}
        for agent in out:
            agent.dup_number = 0
            groups.setdefault(agent.base_headline.casefold(), []).append(agent)
        for same in groups.values():
            if len(same) > 1:
                for number, agent in enumerate(same, 1):
                    agent.dup_number = number
        return out

    def snapshot(self) -> list[dict]:
        return [a.to_dict() for a in self.agents()]

    def page_count(self) -> int:
        with self._lock:
            if not self._agents:
                return 1
            return max(a.slot for a in self._agents.values()) // self.page_size + 1

    def page(self, index: int) -> list[Agent | None]:
        """The agents on keys 0..page_size-1 of page `index` (None = empty key)."""
        keys: list[Agent | None] = [None] * self.page_size
        base = index * self.page_size
        for agent in self.agents():
            if base <= agent.slot < base + self.page_size:
                keys[agent.slot - base] = agent
        return keys

    def waiting(self) -> list[Agent]:
        """The agents that wait for the user, by key."""
        return [a for a in self.agents() if a.state == AgentState.WAITING]

    def next_waiting(self, after_slot: int | None) -> Agent | None:
        """The waiting agent after `after_slot` in key order, wrapping round; the
        first one when `after_slot` is None. Pressing '+' again moves to the next."""
        waiting = self.waiting()
        if not waiting:
            return None
        if after_slot is not None:
            for agent in waiting:
                if agent.slot > after_slot:
                    return agent
        return waiting[0]

    def waiting_elsewhere(self, index: int) -> bool:
        """True when an agent on another page waits for the user."""
        base = index * self.page_size
        with self._lock:
            return any(a.state == AgentState.WAITING
                       and not base <= a.slot < base + self.page_size
                       for a in self._agents.values())

    # ---- internals -------------------------------------------------------------

    def _free_slot(self) -> int:
        used = {a.slot for a in self._agents.values()}
        slot = 0
        while slot in used:
            slot += 1
        return slot

    def _drop_title_entries(self, vendor_id: str) -> None:
        gone = [k for k, a in self._agents.items()
                if a.vendor == vendor_id and a.source == "title"]
        for k in gone:
            del self._agents[k]
        if gone:
            self.version += 1
