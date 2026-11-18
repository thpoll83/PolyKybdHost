"""States and vendors of the agent registry."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class AgentState(IntEnum):
    """Wire values of cmd 45 op 1 (firmware ai_mode.h). A closed range: the
    firmware NACKs anything above STALE."""
    EMPTY = 0     # no agent on this key
    WORKING = 1   # a turn is running
    WAITING = 2   # the agent waits for the user (permission prompt, question)
    DONE = 3      # a turn finished and the user has not looked since
    IDLE = 4      # finished and seen, or no turn yet
    STALE = 5     # no event for a long time

    @classmethod
    def parse(cls, value) -> "AgentState":
        """An AgentState from its name ("working") or wire value. Raises ValueError."""
        if isinstance(value, AgentState):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return cls(value)
        text = str(value).strip().lower()
        if text in STATE_ALIASES:
            return STATE_ALIASES[text]
        raise ValueError(f"Unknown agent state {value!r}")


# Words a hook or a user may use for a state.
STATE_ALIASES = {
    "working": AgentState.WORKING, "busy": AgentState.WORKING, "running": AgentState.WORKING,
    "waiting": AgentState.WAITING, "attention": AgentState.WAITING, "input": AgentState.WAITING,
    "approval": AgentState.WAITING,
    "done": AgentState.DONE, "finished": AgentState.DONE,
    "idle": AgentState.IDLE, "ready": AgentState.IDLE,
    "stale": AgentState.STALE,
}

# The event a hook reports when a session ends; the registry removes the entry.
ENDED = "ended"


@dataclass(frozen=True)
class Vendor:
    vid: str
    name: str
    short: str            # drawn when no mark is available, at most 4 characters
    slugs: tuple = ()     # app_icons slugs to try for the mark, in order
    # True when the vendor's hooks have no event for a permission prompt, so the
    # registry infers "waiting" from a PreToolUse without a PostToolUse.
    infer_waiting: bool = False


VENDORS = {v.vid: v for v in (
    Vendor("claude-code", "Claude Code", "CC", ("si:claude", "si:anthropic")),
    Vendor("codex", "Codex", "Cdx", ("si:openai",)),
    Vendor("gemini", "Gemini CLI", "Gem", ("si:googlegemini",)),
    Vendor("antigravity", "Antigravity", "AG", ("agent:antigravity",), infer_waiting=True),
    Vendor("copilot", "Copilot CLI", "Cop", ("si:githubcopilot",), infer_waiting=True),
    Vendor("cursor", "Cursor", "Cur", ("si:cursor",), infer_waiting=True),
    Vendor("opencode", "OpenCode", "OC", ("agent:opencode",)),
    Vendor("qwen", "Qwen Code", "Qwn", ("agent:qwen",)),
    Vendor("aider", "Aider", "Aid", ("agent:aider",)),
    Vendor("kimi", "Kimi Code", "Kimi", ("agent:kimi",)),
    Vendor("grok", "Grok Build", "Grok", ("agent:grok",)),
    Vendor("vibe", "Mistral Vibe", "Vibe", ("si:mistralai",)),
)}


def vendor(vid: str) -> Vendor:
    """The vendor entry, or a generic one built from the id."""
    vid = (vid or "").strip().lower()
    if vid in VENDORS:
        return VENDORS[vid]
    return Vendor(vid or "agent", vid or "Agent", (vid or "AI")[:3].capitalize())


# Words a card leaves out of a session title, so the subject fits the key
# (2026-11-18: a card that paged through "Fix the HID reconnect after resume" was
# hard to recognise). English only: a title in another language is shown whole.
_SMALL_WORDS = frozenset(
    "a after an and at before by for from in into is of on or the to via when with".split())
# Small words that are not also common words of another language ("in" and "an"
# are German, "a" is French, Spanish and Italian): a title is English when it has
# one of these or starts with a leading verb.
_ENGLISH_MARKERS = frozenset(
    "after and before for from into is of the to via when with".split())
# A first word that names the kind of work, not the subject.
_LEADING_VERBS = frozenset(
    "add change create debug fix implement improve investigate make refactor remove "
    "review support update write".split())


def card_words(title: str) -> str:
    """The words of `title` a card shows: no small words, and no leading verb such
    as "Fix" or "Add". A title that is not English, or that is made only of such
    words, is returned as it is."""
    title = title or ""
    words = title.split()
    low = [w.lower().rstrip(":,") for w in words]
    if not low or not (low[0] in _LEADING_VERBS or _ENGLISH_MARKERS.intersection(low)):
        return title
    kept = [w for w, lw in zip(words, low) if lw not in _SMALL_WORDS]
    if kept and kept[0].lower().rstrip(":,") in _LEADING_VERBS:
        kept = kept[1:]
    return " ".join(kept) or title
