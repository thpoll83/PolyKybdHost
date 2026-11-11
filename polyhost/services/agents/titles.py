"""Find agents from terminal window titles, with no setup.

Several coding CLIs replace the terminal title with their own state. The patterns
are the ones host#572 routes overlays by (res/overlay_sources/aicli/SOURCES.md).
A title cannot tell "waiting for approval" from "finished" for Claude Code (both
show `✳`), so a title entry reads DONE there; a hook gives the real state.

The registry ignores title entries for a vendor once any hook has reported for
it, so a session is never shown twice.
"""
from __future__ import annotations

import re
import sys
import threading

from polyhost.services.agents.model import AgentState

# Claude Code: "✳ <topic>" idle, a spinner glyph while working. Qwen Code uses the
# same glyphs followed by U+FE0E, which must not match.
_CLAUDE_IDLE = re.compile(r"^✳(?!\ufe0e)\s*(.*)$")
_CLAUDE_BUSY = re.compile(r"^[⠐-⣿◐-◓·✢✶✻✽](?!\ufe0e)\s+(.+)$")

# (pattern, vendor, state) in order; the first match wins. The topic is group 1
# when the pattern has one. Formats: res/overlay_sources/aicli/SOURCES.md. A
# title that names the CLI but not its state reads IDLE: the agent is there, and
# a hook, when installed, gives the real state.
_RULES = (
    # Gemini CLI: two spaces after the glyph, padded to 80 characters.
    (r"^◇\s+Ready\s*\((.*)\)", "gemini", AgentState.IDLE),
    (r"^✋\s+Action Required\s*(.*)", "gemini", AgentState.WAITING),
    (r"^⏲\s+Working…?\s*(.*)", "gemini", AgentState.WORKING),
    (r"^✦\s+(.*)", "gemini", AgentState.WORKING),
    (r"^Gemini CLI\s*\((.*)\)$", "gemini", AgentState.IDLE),
    # Codex: "[ ! ] Action Required" (blinking to "[ . ]") while blocked on the
    # user; "codex ..." with the shell integration's Codex option.
    (r"^●?\s*\[ [!.] \] Action Required\s*(.*)", "codex", AgentState.WAITING),
    (r"^codex\b\s*[-:|]?\s*(.*)", "codex", AgentState.WORKING),
    # Qwen Code: Claude Code's glyphs followed by U+FE0E. "✳︎" waits for a
    # confirmation, "◐︎" responds; otherwise "Qwen - <dir>".
    (r"^✳\ufe0e\s*(.*)", "qwen", AgentState.WAITING),
    (r"^◐\ufe0e\s*(.*)", "qwen", AgentState.WORKING),
    (r"^Qwen - (.*)", "qwen", AgentState.IDLE),
    # OpenCode: "OpenCode" on the home screen, "OC | <session>" in a session.
    (r"^OpenCode$", "opencode", AgentState.IDLE),
    (r"^OC \| (.+)", "opencode", AgentState.IDLE),
    # GitHub Copilot CLI: "GitHub Copilot", then "🤖 <topic>" ("Copilot: <topic>"
    # in screen-reader mode).
    (r"^GitHub Copilot$", "copilot", AgentState.IDLE),
    (r"^🤖\s+(.+)", "copilot", AgentState.IDLE),
    (r"^Copilot: (.+)", "copilot", AgentState.IDLE),
    # Kimi Code: "Kimi Code" until the session has a title, then only the title,
    # which does not name it.
    (r"^Kimi Code$", "kimi", AgentState.IDLE),
    # Grok Build: parts joined with " - ", always ending with "grok".
    (r"^⚠ Action Required(?: - (.*?))?(?: - grok)?$", "grok", AgentState.WAITING),
    (r"^\S - Thinking(?: - (.*?))? - grok$", "grok", AgentState.WORKING),
    (r"^(?:(.+) - )?grok$", "grok", AgentState.IDLE),
    # Mistral Vibe: "Vibe" idle, ">> Vibe" (up to three symbols) while working.
    (r"^Vibe$", "vibe", AgentState.IDLE),
    (r"^[^\w\s]{1,3}\s*Vibe$", "vibe", AgentState.WORKING),
)
_COMPILED = tuple((re.compile(p), v, st) for p, v, st in _RULES)


def parse_title(title: str):
    """(vendor id, state, topic) for an agent's terminal title, else None."""
    title = (title or "").strip()
    if not title:
        return None
    m = _CLAUDE_IDLE.match(title)
    if m:
        return "claude-code", AgentState.DONE, m.group(1).strip()
    m = _CLAUDE_BUSY.match(title)
    if m:
        return "claude-code", AgentState.WORKING, m.group(1).strip()
    for pattern, vid, state in _COMPILED:
        m = pattern.match(title)
        if m:
            topic = ((m.group(1) or "") if pattern.groups else "").strip()
            if topic.startswith("(") and topic.endswith(")"):
                topic = topic[1:-1].strip()     # Gemini's "(<dir>)"
            return vid, state, topic
    return None


def list_windows():
    """[(window id, title)] for every top-level window, via pywinctl."""
    import pywinctl
    out = []
    for win in pywinctl.getAllWindows():
        try:
            out.append((str(win.getHandle()), win.title or ""))
        except Exception:   # noqa: BLE001 - a window can close while we read it
            continue
    return out


class TitleScanner:
    """Reads all window titles every `interval_s` on its own thread and reports
    the agents it finds. Not started on macOS, where one window query costs
    seconds (CLAUDE.md, window tick), or when pywinctl cannot list windows."""

    def __init__(self, registry, log, interval_s: float = 3.0, lister=list_windows,
                 enabled=lambda: True):
        self._registry = registry
        self._log = log
        self._interval = interval_s
        self._lister = lister
        self._enabled = enabled
        self._stop = threading.Event()
        self._thread = None

    @staticmethod
    def supported() -> bool:
        return sys.platform != "darwin"

    def start(self):
        if self._thread is not None or not self.supported():
            return
        self._thread = threading.Thread(target=self._run, name="agent-titles", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def scan_once(self):
        present = set()
        for wid, title in self._lister():
            parsed = parse_title(title)
            if parsed is None:
                continue
            vid, state, topic = parsed
            session = f"title:{wid}"
            if self._registry.report(vid, session, state, headline=topic, window=wid,
                                     surface="cli", source="title") is not None:
                present.add(session)
        self._registry.drop_missing_titles(present)

    def _run(self):
        failures = 0
        while not self._stop.wait(self._interval):
            if not self._enabled():
                continue
            try:
                self.scan_once()
                failures = 0
            except Exception as e:  # noqa: BLE001 - keep scanning; log once per streak
                failures += 1
                if failures == 1:
                    self._log.info("Agent title scan failed: %s", e)
