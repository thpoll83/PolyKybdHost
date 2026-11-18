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
# are German, "a" French, Spanish and Italian, "is" and "of" Dutch, "to" Polish
# and Czech, "for" Danish and Norwegian, "via" Italian): only a title with one of
# these loses its small words.
_ENGLISH_MARKERS = frozenset("after and before from into the when with".split())


# Brackets a card leaves out (2026-11-18): in a right-to-left title each one would
# have to be mirrored and put in reverse order, and the key has little room. ASCII,
# fullwidth and CJK brackets; quotation marks stay.
_BRACKETS = frozenset("()[]{}<>\uff08\uff09\uff3b\uff3d\uff5b\uff5d\uff1c\uff1e"
                      "\u3008\u3009\u300a\u300b\u300c\u300d\u300e\u300f"
                      "\u3010\u3011\u3014\u3015\u3016\u3017\u3018\u3019\u301a\u301b")


def no_brackets(text: str) -> str:
    """`text` without brackets: each one is a space, so "fix(io)" reads "fix io",
    and runs of spaces become one."""
    return " ".join("".join(" " if c in _BRACKETS else c for c in text or "").split())


def card_words(title: str) -> str:
    """The words of `title` a card shows: in a title with an _ENGLISH_MARKERS word,
    no small words after the first word. Any other title is returned as it is.
    The first word stays, also a verb such as "Fix" or a small word (2026-11-18)."""
    title = title or ""
    words = title.split()
    low = [w.lower().rstrip(":,") for w in words]
    if _ENGLISH_MARKERS.intersection(low) and not all(lw in _SMALL_WORDS for lw in low):
        # The first word stays, also a small word ("After the fix works").
        words = words[:1] + [w for w, lw in zip(words[1:], low[1:], strict=True)
                             if lw not in _SMALL_WORDS]
    return " ".join(words) or title
