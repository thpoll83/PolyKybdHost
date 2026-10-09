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
OVERLAY = "overlay"
# Key of a layered view (see `_layered`) holding the names drawn as Underlays.
UNDERLAYS = "_underlays"
# Layered views of web-app sub-entries, keyed by (id(base), id(sub)); see
# `_layered`. ⚠️ Kept OUT of the entries on purpose: a cache on the sub-entry
# that pointed back at its browser entry would make the handler's
# `last_entry == matched` comparison recurse through the loop.
_LAYERED_CACHE: dict = {}

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


# A trailing release year, as macOS reports Adobe's apps: `Adobe Photoshop 2025`.
_TRAILING_YEAR = re.compile(r"\s+(?:19|20)\d\d$")


def mapping_key(app_name, mapping):
    """The mapping key that `app_name` resolves to, or None.

    An exact match wins. Failing that, a trailing release year is dropped, so one
    `adobe photoshop` key covers `adobe photoshop 2025` and every later release.
    ⚠️ Without it the key would have to be re-added every year, and a missed
    year fails silently: the app simply loads no overlay on macOS.
    """
    if not app_name:
        return None
    if app_name in mapping:
        return app_name
    stripped = _TRAILING_YEAR.sub("", app_name)
    if stripped != app_name and stripped in mapping:
        return stripped
    return None


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


def _phrase_keys(sub_map):
    """``(words, key)`` for each key of a title sub-map, longest phrase first.

    A key may be several words (``Claude Code``, ``Google Docs``). It matches a
    run of whole title words, compared after splitting both on whitespace.
    Longest first, so at one title position ``Claude Code`` is tried before
    ``Claude`` whatever order the YAML lists them in.
    """
    keys = [(str(k).split(), k) for k in sub_map]
    return sorted((kw for kw in keys if kw[0]), key=lambda kw: -len(kw[0]))


class Underlay(str):
    """An overlay file name drawn UNDER a website's overlay: a browser's own file.

    A plain ``str`` everywhere else -- it compares and hashes as the name, so cache
    keys, logs and the mapping file see no difference. The send path reads
    ``underlay`` and asks the keyboard to draw the positions it ends up owning
    dimmed (cmd 33's DIM flag, protocol v23), so the site's own shortcuts stand out
    and the browser's stay readable underneath.
    """
    underlay = True


def as_underlay_path(name, path):
    """``path`` as an Underlay when ``name`` is one: a resolved path keeps the mark."""
    return Underlay(path) if getattr(name, "underlay", False) else path


def _as_list(value):
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _layered(base, sub):
    """``sub`` with ``base``'s overlay UNDERNEATH its own: base files first.

    A web app runs INSIDE the browser, so the browser's own shortcuts (new tab,
    reload, find, zoom...) still work on every site and must stay on the keycaps.
    The site's overlay goes last because template sources resolve last-one-wins
    per (modifier, key) in `send_overlays_mru`: the site wins exactly the keys it
    draws and the browser keeps every other one. Before this, a site entry
    REPLACED the browser's overlay, so opening GitHub took Ctrl+T, Ctrl+L and the
    tab keys off the board.

    Cached by the identity of both entries, so the matcher returns the same
    object on every tick for the same window. The cache holds the entries it is
    keyed by, so an id is never reused while its entry is cached; a mapping
    reload brings new entries, and the size cap keeps the old ones from piling up.
    """
    key = (id(base), id(sub))
    cached = _LAYERED_CACHE.get(key)
    if cached is not None:
        return cached[2]
    files = []
    site = _as_list(sub.get(OVERLAY))
    # The browser's files become Underlays, drawn dimmed where they show. A file the
    # site lists too is the site's: it keeps its later position and full strength.
    for f in [Underlay(f) for f in _as_list(base.get(OVERLAY))] + site:
        if f in files:
            # A site entry that repeats a browser file (chatgpt.com/codex lists the
            # browser set) keeps the LATER position, so it still wins its keys.
            files.remove(f)
        files.append(f)
    view = dict(sub)
    view[OVERLAY] = files
    # An Underlay compares equal to its plain name, so two views whose files
    # differ only in which are marked would compare equal, and the handler's
    # `last_entry == matched` would skip the resend that changes the dimming.
    # The marked names, as plain strings, make that difference visible.
    view[UNDERLAYS] = tuple(str(f) for f in files if getattr(f, "underlay", False))
    if len(_LAYERED_CACHE) > 512:
        _LAYERED_CACHE.clear()
    _LAYERED_CACHE[key] = (base, sub, view)
    return view


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
    title-matched entry otherwise (never a false positive). Conversely, when a
    URL *is* known, an entry declaring ``urls-contains`` skips its
    ``titles-contains`` fallback: the URL has already answered which site this
    is, so a stray word in the title must not overrule it.

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
                    return _layered(entry, m) if has_overlay else m

    # Split unconditionally: each branch below gates on its own `has_*` flag, so
    # a gate here would have to list every word-based matcher and stay in sync
    # with them. It didn't — `has_contains` was missing, so a contains-only entry
    # never split and its sub-map was unreachable (the shipped browser entry's
    # Miro/Outlook/Jira keys had never once matched). Dropping the gate removes
    # that failure mode rather than re-arming it with one more term.
    words = title.split() if title else []
    if words:
        if has_starts_with:
            for kw, key in _phrase_keys(entry[TITLE_SW]):
                if words[:len(kw)] == kw:
                    m = find_matching_entry(title, entry[TITLE_SW][key], url, os_name)
                    if m is not None:
                        return m
        if has_ends_with:
            for kw, key in _phrase_keys(entry[TITLE_EW]):
                if words[-len(kw):] == kw:
                    m = find_matching_entry(title, entry[TITLE_EW][key], url, os_name)
                    if m is not None:
                        return m
        # `titles-contains` is the weakest signal here — any single word anywhere
        # in the title — so for an entry that also declares `urls-contains` it is
        # a fallback for when the URL is *unknown*, not merely unmatched. A known
        # URL that hit no needle above is positive evidence about which site this
        # is, and it outranks a word: on google.com searching for "jira" the
        # title contains "Jira" while the URL says plainly that it is not Jira.
        # Entries with no `urls-contains` are unaffected -- `url_decided` is
        # False for them whatever the URL is -- as are the two positional
        # matchers above, which no shipped entry combines with `urls-contains`.
        url_decided = bool(has_urls_contains and url)
        # Scan the title left to right, so the earliest key in the title wins
        # as before; at each position the longest phrase is tried first.
        if has_contains and not url_decided:
            keys = _phrase_keys(entry[TITLE_HAS])
            for i in range(len(words)):
                for kw, key in keys:
                    if words[i:i + len(kw)] == kw:
                        m = find_matching_entry(title, entry[TITLE_HAS][key], url, os_name)
                        if m is not None:
                            # On a BROWSER entry (it declares urls-contains) this
                            # is the same web-app routing with no URL known, so
                            # the site layers over the browser here too. Other
                            # apps' title sub-maps keep replacing: a dialog or a
                            # mode of one app is not running inside another.
                            if has_urls_contains and has_overlay:
                                return _layered(entry, m)
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
