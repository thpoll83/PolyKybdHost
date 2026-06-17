import re
from enum import Enum


# Keys in the *annotated* overlay mapping produced by OverlayHandler.annotate().
TITLE = "title"
TITLE_SW = "titles-startswith"
TITLE_EW = "titles-endswith"
TITLE_HAS = "titles-contains"
FLAGS = "flags"


class OverlayCommand(Enum):
    """Command for overlay to turn on or off"""

    NONE = 0
    OFF_ON = 1
    DISABLE = 2
    ENABLE = 3


class Flags(Enum):
    """Overlay flags"""

    HAS_OVERLAY = 0
    HAS_REMOTE = 1
    HAS_TITLE = 2
    HAS_TITLES_STARTS_W = 3
    HAS_TITLES_ENDS_W = 4
    HAS_TITLES_CONTAINS = 5


def find_matching_entry(title, entry):
    """Return the deepest mapping entry that matches ``title``, or ``None``.

    The single window-matcher shared by local (`OverlayHandler`) and remote
    (`RemoteHandler`) tracking — previously two near-identical copies that could
    drift. Pure (no side effects), so it is unit-testable without a display;
    callers add the ENABLE/OFF_ON decision and the current/last bookkeeping.

    ``entry[FLAGS]`` is the 6-bool list
    ``[has_overlay, has_remote, has_title, has_starts_with, has_ends_with,
    has_contains]`` from ``annotate()``; the title sub-maps hold further
    annotated entries. An entry matches when it carries an overlay/remote and,
    if it has a title constraint, the title satisfies it — recursing into the
    starts-with / ends-with / contains sub-maps first (first match wins).

    Raises ``re.error`` if an entry's ``title`` regex is invalid; callers log it
    and treat it as no match (mirrors the previous behaviour)."""
    (has_overlay, has_remote, has_title,
     has_starts_with, has_ends_with, has_contains) = entry[FLAGS]

    if not (has_overlay or has_remote):
        return None

    words = title.split() if (title and (has_starts_with or has_ends_with)) else []
    if words:
        if has_starts_with and words[0] in entry[TITLE_SW]:
            m = find_matching_entry(title, entry[TITLE_SW][words[0]])
            if m is not None:
                return m
        if has_ends_with and words[-1] in entry[TITLE_EW]:
            m = find_matching_entry(title, entry[TITLE_EW][words[-1]])
            if m is not None:
                return m
        if has_contains:
            for word in words:
                if word in entry[TITLE_HAS]:
                    m = find_matching_entry(title, entry[TITLE_HAS][word])
                    if m is not None:
                        return m

    if title and has_title and not re.search(entry[TITLE], title):
        return None
    return entry
