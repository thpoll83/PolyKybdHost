import re
from enum import Enum


# Keys in the *annotated* overlay mapping produced by OverlayHandler.annotate().
TITLE = "title"
TITLE_SW = "titles-startswith"
TITLE_EW = "titles-endswith"
TITLE_HAS = "titles-contains"
# URL constraints — only ever satisfiable when a URL is known for the focused
# window (a browser reporting its active tab, see handler/browser_url.py). URL
# is a regex constraint on the whole URL (like TITLE); URL_HAS is a substring
# sub-map (like TITLE_HAS, but matched by `substr in url` since URLs have no
# word boundaries to split on).
URL = "url"
URL_HAS = "urls-contains"
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
    HAS_URL = 6
    HAS_URLS_CONTAINS = 7


def find_matching_entry(title, entry, url=None):
    """Return the deepest mapping entry that matches ``title`` (and ``url``), or
    ``None``.

    The single window-matcher shared by local (`OverlayHandler`) and remote
    (`RemoteHandler`) tracking — previously two near-identical copies that could
    drift. Pure (no side effects), so it is unit-testable without a display;
    callers add the ENABLE/OFF_ON decision and the current/last bookkeeping.

    ``entry[FLAGS]`` is the 8-bool list
    ``[has_overlay, has_remote, has_title, has_starts_with, has_ends_with,
    has_contains, has_url, has_urls_contains]`` from ``annotate()``; the title
    and url sub-maps hold further annotated entries. An entry matches when it
    carries an overlay/remote and every constraint it declares is satisfied —
    recursing into the more-specific sub-maps first (first match wins):
    ``urls-contains`` before the title sub-maps, because a URL identifies a
    browser web-app far more reliably than its window title.

    ``url`` is the focused window's URL when known (a browser reporting its
    active tab), else ``None``. A ``url``/``urls-contains`` constraint is
    *never* satisfied when ``url`` is ``None`` — so a browser-web-app entry only
    fires once the URL is actually available, and degrades to the plain
    title-matched entry otherwise (never a false positive).

    Raises ``re.error`` if an entry's ``title``/``url`` regex is invalid;
    callers log it and treat it as no match (mirrors the previous behaviour)."""
    flags = entry[FLAGS]
    (has_overlay, has_remote, has_title,
     has_starts_with, has_ends_with, has_contains) = flags[:6]
    # URL flags appended later; tolerate a legacy 6-element annotation (no URL
    # keys) so any older/hand-built annotated entry still matches.
    has_url = len(flags) > 6 and flags[6]
    has_urls_contains = len(flags) > 7 and flags[7]

    if not (has_overlay or has_remote):
        return None

    # URL sub-map first: a browser tab's URL is the strongest signal for which
    # web-app is focused (mail.google.com > "Inbox (3)"). Substring match — URLs
    # have no whitespace to word-split, unlike the title sub-maps below.
    if has_urls_contains and url:
        for needle, sub in entry[URL_HAS].items():
            if needle in url:
                m = find_matching_entry(title, sub, url)
                if m is not None:
                    return m

    words = title.split() if (title and (has_starts_with or has_ends_with)) else []
    if words:
        if has_starts_with and words[0] in entry[TITLE_SW]:
            m = find_matching_entry(title, entry[TITLE_SW][words[0]], url)
            if m is not None:
                return m
        if has_ends_with and words[-1] in entry[TITLE_EW]:
            m = find_matching_entry(title, entry[TITLE_EW][words[-1]], url)
            if m is not None:
                return m
        if has_contains:
            for word in words:
                if word in entry[TITLE_HAS]:
                    m = find_matching_entry(title, entry[TITLE_HAS][word], url)
                    if m is not None:
                        return m

    # A hard ``url`` regex constraint can only be satisfied when a URL is known;
    # with no URL it simply doesn't match (not a false positive). ``urls-contains``
    # is NOT a hard constraint — like ``titles-contains`` it only refines via its
    # sub-map above and otherwise falls through to this entry's own overlay, so a
    # browser entry with a default overlay + urls-contains still matches (default)
    # when the URL is unknown or hits no sub-key.
    if has_url and (not url or not re.search(entry[URL], url)):
        return None
    if title and has_title and not re.search(entry[TITLE], title):
        return None
    return entry
