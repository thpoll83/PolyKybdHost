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
# OS sub-map. An app's keymap is a property of the platform it runs on, not of the
# window — macOS Sublime binds Cmd where Windows Sublime binds Ctrl — so the same
# app name needs different overlay artwork per OS. Keys are canonical OS names
# (see `normalize_os`); the sub-entry may itself carry title/url constraints.
OS = "os"
FLAGS = "flags"

# Accepted spellings -> canonical name. The mapping file is hand-written, so take
# the obvious synonyms rather than making the author guess our internal wording.
_OS_ALIASES = {
    "windows": "windows", "win": "windows", "win32": "windows",
    "macos": "macos", "mac": "macos", "darwin": "macos", "osx": "macos", "os x": "macos",
    "linux": "linux", "bsd": "linux",
    "linux_gnome": "linux_gnome", "linux-gnome": "linux_gnome", "gnome": "linux_gnome",
    "linux_kde": "linux_kde", "linux-kde": "linux_kde", "kde": "linux_kde",
    "plasma": "linux_kde",
    # Deliberately no android/ios. OsType has them, but they can never reach this
    # matcher: get_host_os() never returns them (the host app doesn't run there)
    # and a forwarder is another instance of this same app. They only exist for
    # firmware-side detection / a manual pin on the keyboard. An `android:` branch
    # would therefore be dead config, so it stays unrecognised -> no match.
}
# OsType.name -> canonical name, one-to-one. The Linux desktop-environment
# refinements stay DISTINCT here so a mapping can target GNOME or KDE alone;
# `os_match_keys` is what lets a plain `linux:` branch still catch them.
_OSTYPE_NAMES = {
    "WINDOWS": "windows", "MACOS": "macos", "LINUX": "linux",
    "LINUX_GNOME": "linux_gnome", "LINUX_KDE": "linux_kde",
}
# Canonical name -> broader family to fall back on. Only the Linux desktop
# environments have one: GNOME and KDE bind Super differently (which is why the
# firmware distinguishes them at all), but for most app artwork they are just
# Linux, and an author should not have to spell out all three.
_OS_FAMILY = {"linux_gnome": "linux", "linux_kde": "linux"}


def normalize_os(value):
    """Canonical lowercase OS name for a mapping key, an ``OsType``, or its wire int.

    Returns None for anything unrecognised (including ``OsType.UNKNOWN`` and its
    wire value 0), which callers treat as "no OS known" -> the OS sub-map is
    skipped and the entry's own overlay applies. That is deliberate: an unknown OS
    must fall back to the default artwork, never match an OS branch by accident.
    """
    if value is None:
        return None
    name = getattr(value, "name", None)          # OsType member
    if name is not None:
        return _OSTYPE_NAMES.get(name)
    if isinstance(value, bool):                  # bool is an int; never an OS
        return None
    if isinstance(value, int):                   # OsType wire value
        try:
            from polyhost.device.command_ids import OsType
            return _OSTYPE_NAMES.get(OsType(value).name)
        except (ImportError, ValueError):
            return None
    return _OS_ALIASES.get(str(value).strip().lower())


def os_match_keys(value):
    """Canonical names an ``os:`` branch may use to match `value`, most specific first.

    Running GNOME yields ``["linux_gnome", "linux"]``: a `gnome:` branch wins if
    the mapping has one, otherwise a plain `linux:` branch still applies. Without
    this either the specific key is unreachable (if the DEs collapse to "linux")
    or the general one is (if they don't) — the first version of this collapsed
    them, which silently made a `gnome:` branch fire on KDE too.
    """
    exact = normalize_os(value)
    if not exact:
        return []
    family = _OS_FAMILY.get(exact)
    return [exact, family] if family else [exact]


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
    HAS_OS = 8


def find_matching_entry(title, entry, url=None, os_name=None):
    """Return the deepest mapping entry that matches ``title`` (and ``url``), or
    ``None``.

    The single window-matcher shared by local (`OverlayHandler`) and remote
    (`RemoteHandler`) tracking — previously two near-identical copies that could
    drift. Pure (no side effects), so it is unit-testable without a display;
    callers add the ENABLE/OFF_ON decision and the current/last bookkeeping.

    ``entry[FLAGS]`` is the 9-bool list
    ``[has_overlay, has_remote, has_title, has_starts_with, has_ends_with,
    has_contains, has_url, has_urls_contains, has_os]`` from ``annotate()``; the
    title, url and os sub-maps hold further annotated entries. An entry matches when it
    carries an overlay/remote and every constraint it declares is satisfied —
    recursing into the more-specific sub-maps first (first match wins):
    ``os`` first of all (the platform decides which keymap the app even has),
    then ``urls-contains`` before the title sub-maps, because a URL identifies a
    browser web-app far more reliably than its window title.

    ``url`` is the focused window's URL when known (a browser reporting its
    active tab), else ``None``. A ``url``/``urls-contains`` constraint is
    *never* satisfied when ``url`` is ``None`` — so a browser-web-app entry only
    fires once the URL is actually available, and degrades to the plain
    title-matched entry otherwise (never a false positive).

    ``os_name`` is the OS running the focused app (``OsType``, its wire int, or
    a name); ``None``/unknown skips the ``os`` sub-map entirely, so an entry
    always degrades to its own default artwork rather than guessing.

    Raises ``re.error`` if an entry's ``title``/``url`` regex is invalid;
    callers log it and treat it as no match (mirrors the previous behaviour)."""
    flags = entry[FLAGS]
    (has_overlay, has_remote, has_title,
     has_starts_with, has_ends_with, has_contains) = flags[:6]
    # URL flags appended later; tolerate a legacy 6-element annotation (no URL
    # keys) so any older/hand-built annotated entry still matches.
    has_url = len(flags) > 6 and flags[6]
    has_urls_contains = len(flags) > 7 and flags[7]
    has_os = len(flags) > 8 and flags[8]

    if not (has_overlay or has_remote):
        return None

    # OS sub-map first. Which *keymap* an app uses is decided by the platform it
    # runs on, before anything about the window: macOS Sublime binds Cmd where
    # Windows Sublime binds Ctrl, so the Ctrl artwork is simply wrong on a Mac.
    # An OS branch that needs a window constraint too nests title/url INSIDE
    # itself, which is why this recurses rather than just swapping the overlay.
    # `os_name` is the OS of the machine running the app -- the forwarder's OS
    # for a forwarded window, the local OS otherwise -- so a Mac forwarding to a
    # Windows keyboard host still gets the Mac artwork.
    if has_os and os_name:
        # Most specific first: on GNOME a `gnome:` branch beats a `linux:` one,
        # and a mapping that only has `linux:` still applies.
        for want in os_match_keys(os_name):
            for needle, sub in entry[OS].items():
                if normalize_os(needle) == want:
                    m = find_matching_entry(title, sub, url, os_name)
                    if m is not None:
                        return m

    # URL sub-map first: a browser tab's URL is the strongest signal for which
    # web-app is focused (mail.google.com > "Inbox (3)"). Substring match — URLs
    # have no whitespace to word-split, unlike the title sub-maps below.
    if has_urls_contains and url:
        for needle, sub in entry[URL_HAS].items():
            if needle in url:
                m = find_matching_entry(title, sub, url, os_name)
                if m is not None:
                    return m

    # Split unconditionally: each branch below gates on its own `has_*` flag, so
    # a gate here would have to list every word-based matcher and stay in sync
    # with them. It didn't — `has_contains` was missing, so a contains-only entry
    # never split and its sub-map was unreachable (the shipped browser entry's
    # Miro/Outlook/Jira keys had never once matched). Dropping the gate removes
    # that failure mode rather than re-arming it with one more term.
    words = title.split() if title else []
    if words:
        if has_starts_with and words[0] in entry[TITLE_SW]:
            m = find_matching_entry(title, entry[TITLE_SW][words[0]], url, os_name)
            if m is not None:
                return m
        if has_ends_with and words[-1] in entry[TITLE_EW]:
            m = find_matching_entry(title, entry[TITLE_EW][words[-1]], url, os_name)
            if m is not None:
                return m
        if has_contains:
            for word in words:
                if word in entry[TITLE_HAS]:
                    m = find_matching_entry(title, entry[TITLE_HAS][word], url, os_name)
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
