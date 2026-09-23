"""Fetch the focused PROGRAM's own mark on demand, cache it, render a keycap.

The sibling of `icon_catalog`, and deliberately a separate module: that one
turns a *shortcut concept* into a corner glyph from Material Symbols, this one
turns an *application* into its brand mark. Different catalog, different licence,
different geometry, and only one of them can ever draw on ESC.

Catalog: Simple Icons (CC0-1.0) -- one monochrome `<path>` on a 24x24 viewBox,
which is exactly what a 1-bit 72x40 panel can carry.

⚠️ THE VERSION IS PINNED, and not for reproducibility -- v16 REMOVED brands.
Measured 2026-09-10 against the CDN's own `data/simple-icons.json`: 15.22.0 has
3383 entries including Slack, 16.30.0 has 3459 and Slack is **gone**. So a newer
pin is not a superset, and `@latest` is not a safe default even though today it
happens to resolve to 15.22.0 (`x-jsd-version: 15.22.0`) -- the moment npm's
`latest` tag moves, every mark v16 dropped disappears with no error anywhere.
Re-measure before moving the pin; do not assume forward compatibility.

⚠️ SIMPLE ICONS HAS NO MICROSOFT AND NO ADOBE AT ALL -- measured by substring
over the whole collection, not just by slug: **zero** of its 3383 entries contain
"microsoft", "adobe", "photoshop", "excel" or "outlook", in either version. The
only "word" hits are 1Password, what3words and WordPress. Those are among the
most used apps here, so it is a hole rather than a long tail.

**Material Design Icons (`mdi`, Apache-2.0) is the second source, and it closes
exactly that hole.** It carries the whole `microsoft-*` family -- word, excel,
powerpoint, outlook, onenote, teams, edge, visual-studio, visual-studio-code --
as monochrome single-path 24x24 glyphs, i.e. the same shape this renderer already
consumes. Rendered at 40x40 1-bit they read BETTER than several Simple Icons
marks, because they are drawn for small monochrome use in the first place.

Between the two catalogs Simple Icons is tried FIRST: it is the real brand mark
where it exists, and mdi's version is an interpretation of it. Adobe stays mostly
uncovered (mdi has `adobe` and `adobe-acrobat` and nothing else).

⚠️ **But NEITHER catalog is asked first any more.** The OS's own icon for the
running process (`os_app_icon` -- the exe's resource icon on Windows, the
`.desktop`/hicolor theme on Linux, the bundle's `.icns` on macOS) is exact by
construction, so `program_overlay` reads that and only falls through to a catalog
when it is missing or does not survive 1-bit. What makes that order safe is
`icon_binarise.MIN_SCORE`; see `program_overlay`.

Geometry: the mark occupies the RIGHT-HAND 38x38 SQUARE of the panel and the
left 34 px stay the legend's. The CEILING is arithmetic, not taste: ESC (U+238B)
inks x 2..27, and `copy_overlay_to_buffer` clears a Chebyshev-3 courtyard around
the overlay's ink before drawing it -- so the icon's ink must start at x >= 31
for the clear to begin at 28, one column past the glyph. 72 - 31 = 41, i.e. 40
is the largest box that fits. Measured over 36 marks: at 40 all 36 leave ESC
untouched, at 44 only 20 do.

⚠️ **38 ships, not that ceiling of 40, and the difference is a MARGIN rather
than a clearance.** At 40 a mark that is square in its viewBox inks the panel's
full height edge to edge -- measured, 10 of 15 shipped marks did, with no top or
bottom border at all -- so the keycap read as a picture cropped to the panel
rather than an icon sitting on it. Reported from hardware as "a bit too big"
(2026-09-14). Dropping two pixels buys a 1 px border top and bottom and moves the
left edge 32 -> 34, i.e. MORE ESC clearance, so it can only improve the
courtyard arithmetic above. A wordmark (KiCad, Zoom) loses two pixels of a
dimension it was never short of.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import urllib.error
import urllib.request

CDN_VERSION = "15.22.0"

# source -> URL template. Ordered by preference in `candidates()`, not here.
SOURCES = {
    "si": f"https://cdn.jsdelivr.net/npm/simple-icons@{CDN_VERSION}/icons/{{name}}.svg",
    "mdi": "https://api.iconify.design/mdi/{name}.svg",
}
DEFAULT_SOURCE = "si"

# A THIRD source, and the only one that is not a catalog on the internet: marks
# shipped in this repo, under `res/icons/program/`.
#
# ⚠️ It is a CATALOG, not a name->slug map, and the distinction is the one
# `docs/generic-icons-plan.md` turns on. The file is named after the app's own
# slug -- `terminal.svg` answers `poly:terminal` -- so there is no table to
# groom and a user can drop their own mark in for an application we have never
# heard of. That is the plan's own test for whether something belongs.
#
# It exists because four of the five marks a macOS desktop actually needs are
# in NEITHER catalog under any name `candidates()` derives: Photos, Notes and
# Terminal are 404 in both, and Finder only became reachable by adding the
# `apple-` prefix to MDI_PREFIXES below.
LOCAL_SOURCE = "poly"
PROGRAM_ICON_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "res", "icons", "program")

# ⚠️ A shipped mark may be a finished 72x40 MASK rather than an SVG, and the
# two are read differently. A mark carrying a DITHER cannot be a vector at all
# -- `svg_raster` has no patterns and no opacity, and the panel is one bit, so
# a per-region grey has to be resolved to pixels when the icon is authored.
# Such a mask is loaded VERBATIM: putting a halftone back through
# `icon_binarise` is what turns it into mush.
LOCAL_SUFFIXES = (".svg", ".png")

# ⚠️ The prefixed mdi guesses are what reach Office at all -- an executable named
# `word` has to become `microsoft-word`. They are safe because of what is IN the
# prefix, measured rather than assumed: all 50 `microsoft-*` stems in mdi are
# genuine Microsoft product names (word, excel, teams, edge, azure, xbox, ...),
# and `adobe-*` has exactly one (`acrobat`). The only two stems that are also
# Simple Icons slugs -- `dot-net` and `github` -- are resolved by Simple Icons
# first and never reach this list. Re-run that check before adding a prefix.
#
# ⚠️ `apple-` is the WEAKEST of the three and was added knowing that. Re-run
# 2026-09-22 over mdi's full name list including aliases: 12 `apple-*` entries,
# of which 7 are product names (finder, safari, icloud, ios, ipod, airplay,
# mobileme) and 5 are NOT -- `apple-keyboard-{caps,command,control,option,
# shift}` are modifier symbols. So unlike the other two the family is not all
# brands, and the guard is that a stem has to match one: an application whose
# executable stem is `ios` or `keyboard-caps` would collide. Measured as worth
# it because `mdi:apple-finder` is the ONLY Finder mark in either catalog and
# nothing could reach it -- `si:finder` is a 404 and a one-word display name is
# refused the bare mdi form by the hyphen rule below.
MDI_PREFIXES = ("microsoft-", "adobe-", "apple-")

HTTP_TIMEOUT = 15

# ⚠️ LOAD-BEARING, not politeness -- the Iconify API answers **403 to
# `Python-urllib/3.11`** and 200 to anything else, so without this the whole
# second catalog is silently unreachable and every Office app reads as "no
# icon". (Same class of trap as icon_catalog's TTF_USER_AGENT, where the UA
# decides the FORMAT Google serves.) Measured against both endpoints: jsdelivr
# does not care either way.
USER_AGENT = "PolyKybdHost"

PANEL_W, PANEL_H = 72, 40

# The right-hand square the mark is fitted into (see the courtyard arithmetic
# above). Not a setting: 40 is the hard ceiling -- past it the courtyard clear
# eats the ESC glyph -- and going far below it wastes panel on the only keycap
# whose legend nothing else competes for. 38 leaves a 1 px border so the mark
# reads as an icon on the keycap rather than a picture cropped to it.
PROGRAM_ICON_BOX = 38
PROGRAM_ICON_BOX_MAX = 40

# Rasterise larger and scale the INK down, rather than rendering straight into
# the box: a mark drawn with padding inside its viewBox then still fills the
# panel, and the downscale supersamples instead of aliasing. 3x is free at this
# size (120x120).
SUPERSAMPLE = 3

# Alpha level counted as ink. 96 was tried and thickens strokes enough to close
# the counters on a detailed mark (GIMP's face); 128 keeps them open.
INK_THRESHOLD = 128

_SLUG_RE = re.compile(r"[^a-z0-9]")
_VERSION_SUFFIX_RE = re.compile(r"[-_ ]?\d+(\.\d+)*$")
_EXE_SUFFIX_RE = re.compile(r"\.(exe|app|bin)$")

# ⚠️ `os_app_icon` is deliberately NOT imported here. Since E2 this module
# takes a resolved `AppIdentity` rather than a pid, so it needs nothing from
# that module at all -- which is the sharper form of the boundary the
# docstring describes: the lookup finds bytes, this side renders them, and
# the dependency runs one way only (see `tools/os_icon_probe.py`).
from polyhost.handler.own_process import POLYHOST_APP
from polyhost.services import icon_binarise
from polyhost.util.https import ssl_context

log = logging.getLogger("PolyHost")


def auto_fetch_enabled() -> bool:
    """May this install reach the network for a mark it has not cached?

    ⚠️ The switch is over RETRIEVING, not over the feature. Off means cache-only:
    apps already fetched keep their icon, a new one simply gets none. Turning it
    off on a metered or air-gapped machine must not take away icons already held.
    """
    try:
        from polyhost.settings import read_setting
        return bool(read_setting("shortcut_icon_auto_fetch", True))
    except Exception:
        return True


def default_cache_dir() -> str:
    """Per-user cache for fetched marks, beside the shortcut-icon font cache."""
    try:
        import platformdirs
        base = platformdirs.user_cache_dir("PolyKybd", "PolyTasten")
    except Exception:
        base = os.path.join(os.path.expanduser("~"), ".cache", "PolyKybd")
    return os.path.join(base, "icons", "apps")


def normalise(app_name: str) -> str:
    """An application name reduced to a Simple Icons slug candidate.

    Simple Icons derives a slug from the brand title by lowercasing and dropping
    every non-alphanumeric, so the same reduction applied to an executable name
    lands on the slug whenever the two agree ("Inkscape" -> `inkscape`).

    Three reductions before that, each measured against real application names
    rather than invented:

    * a reverse-DNS application id keeps only its last component, so the Linux
      desktop/flatpak ids `org.gimp.GIMP` and `org.inkscape.Inkscape` resolve at
      all (as themselves they reduce to `orggimpgimp`, which is nothing);
    * an `.exe`/`.app`/`.bin` suffix goes, since the tracker hands the raw
      executable name through on some platforms;
    * a trailing version goes, which is what collapses `gimp-2.0`, `gimp-2.8`,
      `gimp-3.0` and `clion64` onto one mark.
    """
    name = (app_name or "").strip().lower()
    if not name:
        return ""
    if name.count(".") >= 2 and not name.endswith((".exe", ".app", ".bin")):
        name = name.rsplit(".", 1)[-1]          # org.gimp.GIMP -> gimp
    name = _EXE_SUFFIX_RE.sub("", name)
    name = _VERSION_SUFFIX_RE.sub("", name)
    return _SLUG_RE.sub("", name)


def kebab(app_name: str) -> str:
    """An application name in mdi's naming: lowercase words joined by '-'.

    The two catalogs name the same brand differently -- Simple Icons drops every
    separator (`visualstudiocode`), mdi keeps them (`visual-studio-code`) -- so a
    single normalised form cannot address both.
    """
    name = (app_name or "").strip().lower()
    if not name:
        return ""
    if name.count(".") >= 2 and not name.endswith((".exe", ".app", ".bin")):
        name = name.rsplit(".", 1)[-1]
    name = _EXE_SUFFIX_RE.sub("", name)
    name = _VERSION_SUFFIX_RE.sub("", name)
    return re.sub(r"[^a-z0-9]+", "-", name).strip("-")


def candidates(app_name: str, names=()) -> list:
    """Qualified `source:name` icons to try, in order, for one application.

    `names` are the application's OS-reported DISPLAY names, best first (see
    `os_app_icon.display_names`). They are tried BEFORE the executable name
    because they are a far better key: `kebab("Microsoft Word")` is mdi's own
    `microsoft-word`, which `winword` can never reach. Measured over 16
    realistic display names, 14 resolve with no map at all.

    The list is a preference order, not a set of equals -- Simple Icons carries
    the real brand mark where it has one, and mdi's is an interpretation of it.

    ⚠️ There is NO name->slug map any more, deliberately. 70 hand-written
    entries bought 73% coverage over 151 probed names and made every unheard-of
    application a 71st entry; `docs/generic-icons-plan.md` has the measurement
    and the reversal.
    """
    out = []

    def offer(value):
        if value and value not in out:
            out.append(value)

    for display in names:
        slug = normalise(display)
        if slug:
            offer(f"si:{slug}")
        stem = kebab(display)
        # ⚠️ The BARE mdi name is admitted for a display name ONLY when it is
        # MULTI-SEGMENT, and that hyphen is the whole safety rule. mdi is 7400
        # icons of which most are generic UI symbols, so a bare hit is not
        # evidence of a brand -- and a display name fails in exactly that
        # direction: measured on a stock container, `yelp` reports "Help" and
        # `xdg-desktop-portal-gtk` reports "Portal", while `mdi:help` and
        # `mdi:settings` both return 200. Requiring a hyphen keeps
        # `microsoft-word` and `visual-studio-code` and refuses those.
        # Measured: 13/14 of the real names still resolve, 1/10 generic ones leak.
        if "-" in stem:
            offer(f"mdi:{stem}")

    guess = normalise(app_name)
    if guess:
        offer(f"si:{guess}")
    stem = kebab(app_name)
    if stem:
        # For the EXECUTABLE name the bare mdi form stays refused outright --
        # it has none of the display name's multi-word structure to lean on, so
        # `code` would resolve to a generic `</>` glyph. Only the provably-brand
        # prefixed families are guessed; every stem behind them is a product name.
        for prefix in MDI_PREFIXES:
            offer(f"mdi:{prefix}{stem}")

    # The shipped marks go LAST. With `program_overlay` ranking by legibility
    # the order is only a tie-break, but the tie should go to a real brand mark
    # over a generic one of ours.
    for display in names:
        slug = normalise(display)
        if slug:
            offer(f"{LOCAL_SOURCE}:{slug}")
    if guess:
        offer(f"{LOCAL_SOURCE}:{guess}")
    return out


def qualify(name: str) -> str:
    """`source:name`, defaulting an unqualified value to Simple Icons.

    Lets one map entry name either catalog -- `chrome: googlechrome` and
    `winword: mdi:microsoft-word` -- without a second file or a second column.
    """
    return name if ":" in name else f"{DEFAULT_SOURCE}:{name}"


def os_slug(source: str, icon: bytes) -> str:
    """The cache key for an OS-supplied mark: a name AND a content digest.

    ⚠️ **THE SLUG IS THE MRU CACHE KEY, so it has to identify the ICON, not the
    file it came out of** — `synthetic_overlay`'s docstring states that rule and
    the basename alone does not satisfy it on macOS, where nearly every system
    app ships its icon as literally `AppIcon.icns`:

        /System/Applications/Maps.app/Contents/Resources/AppIcon.icns
        /System/Applications/Photos.app/Contents/Resources/AppIcon.icns
        /System/Applications/Notes.app/Contents/Resources/AppIcon.icns

    All three used to slug to `os:AppIcon.icns`, so the MRU filed Maps' mark
    under that key and then served it to Photos, Notes, Safari and every other
    system app — an MRU HIT, no upload, nothing in the log to notice. Reported
    from the field as "the maps icon kept showing for every following app"
    (2026-09-21). Terminal was the one that looked right, purely because its
    file happens to be called `Terminal.icns`.

    ⚠️ The digest is of the ICON BYTES, not of the path, and that is the better
    half of the fix: two apps that genuinely ship the same icon still share one
    pool slot, and an icon that CHANGES under a fixed path — a theme switch —
    gets a new slug and is redrawn instead of being served stale from the
    cache. The forwarded path already keys this way for the same reason
    (`app_icon_fetcher._as_identity`); this makes the local path match it.

    The basename is kept in front of the digest so the log still says which
    file was read.
    """
    name = os.path.basename(source) or "icon"
    digest = hashlib.sha256(icon or b"").hexdigest()[:12]
    return "os:%s@%s" % (name, digest)


def split_name(qualified: str) -> tuple:
    source, _, name = qualify(qualified).partition(":")
    return source, name


def _is_svg(data: bytes) -> bool:
    """Refuse anything that is not an SVG document.

    Same discipline as `icon_catalog._is_ttf` and `font_downloader`'s sfnt check:
    a proxy error page returning 200 would otherwise be cached under the mark's
    name and fail at render time, where the cause is invisible.
    """
    head = data[:512].lstrip()
    return head.startswith(b"<?xml") or head.startswith(b"<svg")


def local_icon_path(name: str) -> str | None:
    """The shipped mark of that name, `.svg` before `.png`, or None.

    Never touches the cache dir: these are repo content, not downloads, so an
    unwritable or empty cache cannot make one disappear.
    """
    if not name or os.sep in name or (os.altsep and os.altsep in name) \
            or name.startswith("."):
        # A slug reaches here from an application's own reported name, so it is
        # untrusted input on the way to a filesystem path. `normalise` already
        # strips it to [a-z0-9], but `candidates()` is not the only caller.
        return None
    for suffix in LOCAL_SUFFIXES:
        path = os.path.join(PROGRAM_ICON_DIR, name + suffix)
        if os.path.exists(path):
            return path
    return None


def icon_path(slug: str, cache_dir: str | None = None) -> str:
    """⚠️ The cache filename carries the SOURCE. The two catalogs share names
    (`mdi:slack` and `si:slack` are different drawings of the same brand), so a
    bare name would let whichever was fetched first answer for both."""
    source, name = split_name(slug)
    if source == LOCAL_SOURCE:
        # Not a cache entry at all. Returned anyway so a caller that only wants
        # "which file answered this slug" (the fetcher's log line) still works.
        return local_icon_path(name) or os.path.join(
            PROGRAM_ICON_DIR, f"{name}{LOCAL_SUFFIXES[0]}")
    return os.path.join(cache_dir or default_cache_dir(), f"{source}-{name}.svg")


def fetch_icon(slug: str, cache_dir: str | None = None,
               allow_network: bool | None = None,
               reasons: dict | None = None) -> str | None:
    """Path to the mark's SVG, downloading it once if needed.

    ⚠️ `reasons` is how a MISS becomes diagnosable. Every failure below used to
    be `log.debug` or nothing at all, so at the default level the only thing a
    user saw was the aggregate "the catalog carries none of ..." -- which cannot
    tell a 404 (this brand is not in the catalog, nothing to do) from a refused
    download (network, proxy, an unwritable cache) from the fetch never being
    attempted because auto-fetch is off. Those need opposite actions, and the
    line that reported them was identical. Measured on macOS 2026-09-21:
    `si:googlechrome` is a real slug that answers 200 from here, and the log
    still said only "carries none of" (field).

    Returns None when it is neither cached nor reachable -- and when the catalog
    simply does not carry it, which is an ordinary 404 rather than a fault. The
    caller then draws nothing, so nothing here raises.
    """
    def why(text):
        if reasons is not None:
            reasons[slug] = text
        return None

    if not slug:
        return None
    source, name = split_name(slug)
    if source == LOCAL_SOURCE:
        # Shipped, so there is nothing to download and `allow_network` does not
        # apply -- a mark of ours must draw on an offline machine.
        return local_icon_path(name) or why("no shipped mark of that name")
    if source not in SOURCES:
        # Checked BEFORE the cache, not after: otherwise a file left under an
        # unknown source (a stale name, a hand-dropped file) is served as if the
        # source were real, and the one function that decides what may be fetched
        # answers from disk instead.
        return why("unknown source")
    path = icon_path(slug, cache_dir)
    if os.path.exists(path) and os.path.getsize(path) > 16:
        return path
    if not (auto_fetch_enabled() if allow_network is None else allow_network):
        return why("not cached, and auto-fetch is off")
    url = SOURCES[source].format(name=name)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        # ⚠️ `context=` is load-bearing, not tidiness: a python.org macOS build
        # gives urllib no certificate store, so this died with
        # CERTIFICATE_VERIFY_FAILED on every mark while `requests` worked in the
        # same process. See `util.https`.
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT,
                                    context=ssl_context()) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        log.debug("No catalog mark for '%s' (HTTP %s)", slug, exc.code)
        if exc.code == 404:
            # An ordinary answer, not a fault: this brand is not in the
            # catalog. Nothing to fix, and worth saying so plainly.
            return why("not in the catalog (404)")
        return why("HTTP %s" % exc.code)
    except Exception as exc:
        log.debug("Could not fetch the mark for '%s': %s", slug, exc)
        return why("download failed: %s" % exc)
    if not _is_svg(data):
        # Silent before this: a proxy's error page returning 200 was refused
        # here and reported as if the brand did not exist.
        return why("the download was not an SVG (%d B)" % len(data))
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".part"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)       # never leave a half file under the real name
    except OSError as exc:
        return why("could not be cached: %s" % exc)
    return path


def title_of(svg_path: str) -> str | None:
    """The brand name the catalog gives this mark, from the SVG's own <title>.

    Worth logging beside the slug: with no curated map left, a guess landing on
    the wrong BRAND is the one failure the 404 cannot reject for us, and the
    title is the only thing that would show it.
    """
    try:
        with open(svg_path, encoding="utf-8") as fh:
            head = fh.read(2048)
    except OSError:
        return None
    match = re.search(r"<title>(.*?)</title>", head, re.S)
    return match.group(1).strip() if match else None


def _alpha(svg_path: str, size: int):
    """Coverage for one icon at `size` x `size`, as a uint8 array, or None.

    ⚠️ THE PURE-PYTHON RASTERISER IS PRIMARY, and that is a Windows decision
    rather than a preference. `cairosvg` needs `cairocffi`, which publishes NO
    Windows wheel and bundles no library -- it dlopens `libcairo-2.dll`, absent
    from a stock Windows Python -- so on the platform most of these users are
    on, the import raises and every program icon silently fails to draw.
    `svg_raster` runs on `freetype-py`, already a declared dependency, which
    does ship a Windows wheel with FreeType inside it.

    Making it primary rather than a fallback also means one output everywhere:
    otherwise Linux would draw cairo's rasterisation and Windows FreeType's,
    and the difference would first show up in a screenshot nobody could explain.
    Measured over 29 real icons at the shipping 40x40: the two agree to within
    14 pixels worst case, typically 1-8, all of it antialiasing at the edge.
    cairosvg stays as a fallback for anyone who has it.
    """
    try:
        import numpy as np
        with open(svg_path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except Exception as exc:
        log.debug("Could not read %s: %s", svg_path, exc)
        return None
    try:
        from polyhost.services import svg_raster
        coverage = svg_raster.rasterise(text, size, size)
        if coverage is not None:
            return (coverage * 255).astype("uint8")
    except Exception as exc:
        log.debug("svg_raster could not draw %s: %s", svg_path, exc)
    try:
        import io
        import cairosvg
        from PIL import Image
        png = cairosvg.svg2png(bytestring=text.encode("utf-8"),
                               output_width=size, output_height=size)
        return np.array(Image.open(io.BytesIO(png)).convert("RGBA"))[..., 3]
    except Exception as exc:
        log.debug("No rasteriser could draw %s: %s", svg_path, exc)
        return None


def render_overlay(svg_path: str, box: int = PROGRAM_ICON_BOX):
    """A 40x72 boolean array with the mark right-aligned, everything else blank.

    That shape is what OverlayData consumes, so the result rides the existing
    overlay transport with no firmware change -- and because the left two thirds
    are blank, the ROI is small and the compressed payload well under a frame.
    """
    try:
        import numpy as np
        from PIL import Image
    except Exception:
        log.debug("Cannot render a program icon: Pillow/numpy unavailable")
        return None
    alpha = _alpha(svg_path, box * SUPERSAMPLE)
    if alpha is None:
        return None

    rows = (alpha > 0).any(1).nonzero()[0]
    cols = (alpha > 0).any(0).nonzero()[0]
    if not len(rows) or not len(cols):
        return None
    ink = Image.fromarray(alpha[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1])
    scale = min(box / ink.width, box / ink.height)
    ink = ink.resize((max(1, round(ink.width * scale)),
                      max(1, round(ink.height * scale))), Image.LANCZOS)

    mask = np.zeros((PANEL_H, PANEL_W), dtype=bool)
    width, height = ink.width, ink.height
    x = PANEL_W - width                 # flush right: the courtyard needs x >= 31
    y = max(0, (PANEL_H - height) // 2)
    mask[y:y + height, x:x + width] = np.array(ink) > INK_THRESHOLD
    return mask


def load_mask(path: str):
    """A finished 72x40 overlay mask read VERBATIM from a 1-bit PNG, or None.

    ⚠️ Deliberately no binarisation, no fit and no scaling. This file is already
    the thing `OverlayData` consumes -- it was authored at panel size precisely
    because what it carries (a per-region dither) cannot survive being read as
    a picture and re-thresholded. Anything that is not exactly panel-sized is
    refused rather than resized, because a resize IS a re-threshold.
    """
    try:
        import numpy as np
        from PIL import Image
        with Image.open(path) as image:
            array = np.array(image.convert("L")) > 127
    except Exception as exc:                # noqa: BLE001 - cosmetic lookup
        log.debug("Could not read the mark mask %s: %s", path, exc)
        return None
    if array.shape != (PANEL_H, PANEL_W):
        log.info("Ignoring the mark mask %s: it is %dx%d, not %dx%d",
                 path, array.shape[1], array.shape[0], PANEL_W, PANEL_H)
        return None
    return array if array.any() else None


def render_mark(path: str):
    """The overlay mask for a catalog or shipped mark, whichever form it is in."""
    if path.lower().endswith(".png"):
        return load_mask(path)
    return render_overlay(path)


def mark_rank(mask):
    """The sort key a candidate competes on: `(read_the_right_way_up, score)`.

    ⚠️ POLARITY OUTRANKS SCORE, and that is the fix for "not the fully solid
    icon" (reported from hardware 2026-09-23 after the OS icon stopped winning
    outright). `icon_binarise.score` rates a mostly-ink mark by its HOLES, and
    it rates them well: measured, `si:safari` -- a filled disc with a hairline
    needle -- scores 0.610 inverted, ABOVE `mdi:apple-safari`'s 0.532 compass
    read the right way up. Ranking on score alone therefore picks the blob, and
    no amount of ranking fixes it.
    #
    An inverted reading is not wrong, it just means the art is mostly ink and
    we are reading its holes -- which on a white-on-black keycap IS the big
    solid blob. Measured over the real candidate set, the split is exact: the
    only two marks read inverted are `si:safari` (0.727 lit) and
    `si:gnometerminal` (0.785), the two that looked bad on hardware, while
    every mark that reads well -- both catalogs' compasses, all four shipped
    ones -- is read normally.
    #
    ⚠️ It is a PREFERENCE, not a veto: an inverted candidate still wins when it
    is the only one, which keeps a genuine dark-plate app icon working. And it
    deliberately does NOT try to tell a dark plate from a filled silhouette --
    see `reads_inverted`, where that idea is measured and refuted.
    """
    return (not _reads_inverted(mask), mark_score(mask))


def _reads_inverted(mask) -> bool:
    """`icon_binarise.reads_inverted` over the mark's own ink (see `mark_score`
    for why the crop matters)."""
    try:
        import numpy as np
    except Exception:                       # noqa: BLE001
        return False
    if mask is None or not mask.any():
        return False
    rows, cols = np.flatnonzero(mask.any(1)), np.flatnonzero(mask.any(0))
    return icon_binarise.reads_inverted(
        mask[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1])


def mark_score(mask) -> float:
    """`icon_binarise.score` of a mark, read over ITS OWN ink.

    ⚠️ Cropping matters. The panel's left two thirds are blank by construction,
    so scoring the whole 72x40 deflates every density term and ranks a big mark
    above a legible one. `score()` is written for a mask fitted to its ink.
    """
    try:
        import numpy as np
    except Exception:                       # noqa: BLE001
        return 0.0
    if mask is None or not mask.any():
        return -1.0
    rows, cols = np.flatnonzero(mask.any(1)), np.flatnonzero(mask.any(0))
    return icon_binarise.score(mask[rows[0]:rows[-1] + 1,
                                    cols[0]:cols[-1] + 1])


def _looks_like_svg(data: bytes) -> bool:
    """True for SVG bytes. Delegates -- `icon_binarise` owns the one definition,
    because the forwarder's `shrink_for_transport` routes on it too and a second
    copy that drifted would send one of the two the wrong way."""
    from polyhost.services import icon_binarise
    return icon_binarise.looks_like_svg(data)


def render_os_overlay(data: bytes, box: int = PROGRAM_ICON_BOX):
    """(mask, conversion, score) for an icon the OPERATING SYSTEM gave us.

    The sibling of `render_overlay`, and separate because the two inputs want
    opposite treatment. A catalog mark is a monochrome single-path SVG whose
    ALPHA is the drawing, so silhouette is exactly right. An OS icon is
    full-colour art whose alpha is only its outer shape -- measured, the six
    LibreOffice marks all render as the SAME 94.5%-lit page blob that way -- so
    it has to be read by `icon_binarise`, which picks a conversion per icon.
    """
    try:
        import io
        import numpy as np
        from PIL import Image
        from polyhost.services import icon_binarise
    except Exception:
        log.debug("Cannot render an OS icon: Pillow/numpy unavailable")
        return None, None, -1.0
    if _looks_like_svg(data):
        # ⚠️ Vector goes through the EXISTING rasteriser, not Pillow, which
        # cannot read SVG at all -- and most of a modern Linux icon theme is
        # SVG, so routing it here is the difference between the Linux backend
        # working and scoring -1.00 on nearly everything. `_alpha` is also the
        # right reading for vector art: a themed SVG icon is usually a flat
        # silhouette already, which is the case alpha is exactly correct for.
        import tempfile
        handle, temporary = tempfile.mkstemp(suffix=".svg")
        try:
            with os.fdopen(handle, "wb") as fh:
                fh.write(data)
            mask = render_overlay(temporary, box)
        finally:
            try:
                os.unlink(temporary)
            except OSError:
                pass        # the temp file is the rasteriser's, not the
                            # caller's; a leaked one costs a few KB in the
                            # system temp dir, and raising here would lose the
                            # mask we came for.
        # ⚠️ SCORED like any other candidate, never trusted for being vector.
        # `_alpha` gives coverage, so a themed SVG arrives as its SILHOUETTE --
        # measured, a filled square for gvim and a solid page for LibreOffice,
        # both of which sit at a perfectly ordinary lit fraction and are read
        # as blobs only by the edge term.
        silhouette = (None, None, -1.0)
        if mask is not None:
            silhouette = (mask, "svg",
                          icon_binarise.score(mask[:, PANEL_W - box:]))
        # ⚠️ TWO readings compete, rather than the silhouette winning by being
        # first. A monochrome single-path SVG still wins as a silhouette (its
        # alpha IS the drawing); a full-colour desktop icon loses, which is the
        # whole point -- see `_svg_colour_candidate`. Same scorer for both, so
        # this is the existing five-way contest with a sixth entrant, not a new
        # policy.
        colour = _svg_colour_candidate(data, box)
        best = max((silhouette, colour), key=lambda c: c[2])
        if best[0] is None:
            return None, None, -1.0
        return best
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        log.debug("Could not decode an OS icon (%d bytes): %s", len(data or b""), exc)
        return None, None, -1.0
    # An .ico or .icns holds several sizes; take the largest, since the render
    # downscales and a 16px frame upscaled to 38 is mush.
    try:
        sizes = getattr(image, "info", {}).get("sizes")
        if sizes:
            image.size = max(sizes)
            image.load()
    except Exception:
        pass                            # single-frame image; nothing to choose
    ink, conversion, score = icon_binarise.choose(image, box)
    if ink is None:
        return None, None, score
    return _place_ink(ink), conversion, score


def _place_ink(ink):
    """`ink` seated in the 72x40 panel, flush right and vertically centred."""
    import numpy as np
    mask = np.zeros((PANEL_H, PANEL_W), dtype=bool)
    height, width = ink.shape
    x = PANEL_W - width                 # flush right: the courtyard needs x >= 31
    y = max(0, (PANEL_H - height) // 2)
    mask[y:y + height, x:x + width] = ink
    return mask


# PolyHost's own windows get the PolyKybd mark: the lit keys of the 6x6 grid
# in `res/icons/pcolor.svg`, row by row. The unlit keys spell the P.
#
# Drawn here rather than rasterised from that SVG, because the SVG does not
# survive 1-bit: its dark body plate thresholds into a frame and the key
# gradients dither. 5 px keys on a 6 px pitch give 35 px, inside the 38 px box,
# with a clean 1 px gap between keys. `tests/services/app_icons_test.py` checks
# this table against the SVG.
POLYKYBD_KEYS = (
    "######",
    "#....#",
    "#.##.#",
    "#....#",
    "#.####",
    "######",
)
POLYKYBD_KEY_PX = 5
POLYKYBD_KEY_PITCH = 6
# The slug is the MRU cache key; bump the suffix if the drawing changes.
POLYKYBD_SLUG = "res:polykybd@1"


def polykybd_mark():
    """The PolyKybd mark seated in the 72x40 panel, like any program mark."""
    import numpy as np
    rows = len(POLYKYBD_KEYS)
    cols = len(POLYKYBD_KEYS[0])
    ink = np.zeros((POLYKYBD_KEY_PITCH * (rows - 1) + POLYKYBD_KEY_PX,
                    POLYKYBD_KEY_PITCH * (cols - 1) + POLYKYBD_KEY_PX),
                   dtype=bool)
    for r, row in enumerate(POLYKYBD_KEYS):
        for c, cell in enumerate(row):
            if cell == "#":
                y, x = r * POLYKYBD_KEY_PITCH, c * POLYKYBD_KEY_PITCH
                ink[y:y + POLYKYBD_KEY_PX, x:x + POLYKYBD_KEY_PX] = True
    return _place_ink(ink)


def _svg_colour_candidate(data: bytes, box: int):
    """(mask, conversion, score) for an SVG read as COLOUR ART, or a miss.

    ⚠️ The silhouette is the WRONG reading for an OS icon, and measurably so.
    `render_overlay` takes alpha, which is exactly right for a catalog mark --
    one monochrome path whose alpha IS the drawing -- and throws away everything
    inside a modern desktop icon, which is a filled rounded-rect plate with art
    on top. Measured on the real `org.gnome.TextEditor.svg`: as a silhouette it
    is a 71.8%-lit blob scoring **0.10** and `MIN_SCORE` correctly refuses it,
    so the keycap stayed blank; rasterised in colour and read by `choose` it
    scores **0.48** and draws a recognisable pen. Reported from a live forwarder
    as terminal and the log window showing marks while the text editor did not.

    ⚠️ cairosvg only, and that is not the inconsistency it looks like. `_alpha`
    keeps the pure-Python rasteriser PRIMARY so a catalog mark renders
    identically on every platform, including a Windows box where cairosvg cannot
    install. `svg_raster` fills paths into a coverage mask by construction --
    its own scope note says "a flat, one-colour SVG" -- so it cannot answer this
    question at all. An OS icon comes from THIS machine's theme, so it is
    machine-specific already and cross-platform identity was never a property it
    could have; and Windows app icons are PE resources, not SVG, so the branch
    is barely reachable there. No cairosvg means today's silhouette, unchanged.
    """
    try:
        import io as _io

        import cairosvg
        from PIL import Image
    except Exception:
        return None, None, -1.0
    try:
        # Supersampled for the same reason `_alpha` is: the reduction to `box`
        # is where the antialiasing that survives 1-bit comes from.
        png = cairosvg.svg2png(bytestring=data,
                               output_width=box * SUPERSAMPLE,
                               output_height=box * SUPERSAMPLE)
        ink, conversion, score = icon_binarise.choose(
            Image.open(_io.BytesIO(png)), box)
    except Exception as exc:
        log.debug("Could not rasterise an SVG icon in colour: %s", exc)
        return None, None, -1.0
    if ink is None:
        return None, None, score
    return _place_ink(ink), conversion, score


def program_overlay(app_name: str, identity=None, cache_dir: str | None = None,
                    allow_network: bool | None = None):
    """(mask, source name) for the focused app, or (None, first candidate).

    TWO sources, and the ORDER REVERSED in E2 (see
    `docs/generic-icons-plan.md` B.3):

    1. the app's **own icon, from the OS** -- `identity.icon`, read through
       `icon_binarise`. Exact by construction: no name matching, no network,
       nothing to guess wrong, which is why it now goes first;
    2. the **monochrome catalog** (Simple Icons, then mdi), keyed on the
       OS-reported DISPLAY names and then the executable name.

    ⚠️ The catalog used to be asked FIRST, and the reason was legibility rather
    than certainty: catalog art is one path drawn for small monochrome use and
    cannot be unreadable, while an OS icon is full-colour art that has to
    survive thresholding and measurably not all of it does. **That reasoning
    still holds -- what makes the reversal safe is `MIN_SCORE`**, which refuses
    a bad 1-bit reading and falls through to the catalog instead of drawing a
    blob. Do not remove that gate; it is the only thing standing between
    OS-first and a keycap full of mush.

    ⚠️ It takes the resolved `AppIdentity`, **not a pid**, deliberately. The icon
    and the display names come out of one `os_app_icon.app_identity()` call so
    the mark and whatever the caller captions it with cannot describe two
    different applications -- and on Windows that lookup opens the process and
    reads its resources, which is not a thing to do twice per window change.
    `identity=None` is the honest degradation for a caller that has no pid: only
    the executable name reaches the catalog.

    A name comes back either way so a caller can say which app it failed for.
    """
    # ⚠️ A dict is a PROGRAMMING error here, not an input to tolerate. The
    # forwarded identity arrives as one over the RPC, and the getattr reads
    # below answer every dict with their default -- so it was accepted, ignored
    # and logged as "OS names: <none>". `app_icon_fetcher._as_identity` is the
    # boundary that converts it; this is the guard that stops a second caller
    # from re-introducing the silence. Deliberately narrower than an isinstance
    # check on AppIdentity, which would reject the test doubles.
    if isinstance(identity, dict):
        raise TypeError("program_overlay takes an AppIdentity, not a dict -- "
                        "convert a forwarded identity with _as_identity()")
    # ⚠️ Before the OS icon, because for PolyHost that icon is the Python
    # interpreter's (see `own_process`).
    if app_name == POLYHOST_APP:
        log.info("Program mark for %s: the built-in PolyKybd mark", app_name)
        return polykybd_mark(), POLYKYBD_SLUG
    names = getattr(identity, "names", ()) or ()
    icon = getattr(identity, "icon", None)
    best = None
    if icon:
        mask, conversion, score = render_os_overlay(icon)
        source = getattr(identity, "icon_path", "") or ""
        if mask is not None and score >= icon_binarise.MIN_SCORE:
            # ⚠️ A CANDIDATE, not the answer. Clearing `MIN_SCORE` used to end
            # the search, and that is what a macOS desktop actually looks like
            # reported from hardware (2026-09-23): every system `.icns` clears
            # a floor of 0.08 comfortably while still reading as mush on the
            # panel, so the catalog and the shipped marks were never reached
            # and shipping them changed nothing at all.
            #
            # `MIN_SCORE` still gates, in its own units, the question it was
            # tuned for -- "is this usable AT ALL", i.e. may we draw it when
            # there is nothing else. What it must not do is decide a contest.
            #
            # ⚠️ RE-SCORED with `mark_score` for the ranking, deliberately, and
            # the returned `score` is NOT reused: this module carries two crop
            # conventions -- `choose()` scores a mask fitted to its ink, the SVG
            # silhouette path scores a padded panel slice -- and comparing
            # across sources needs one. The gap is not cosmetic: si:safari reads
            # 0.192 padded and 0.610 tight, because the padding drops it under
            # `MAX_LIT` and `score()` stops inverting it.
            #
            # It is evaluated FIRST and replacement below is strict `>`, so the
            # OS icon keeps ties. That is the "exact by construction" argument
            # from `docs/generic-icons-plan.md` B.3 surviving in the one place
            # it still holds: equally legible, prefer the app's own art.
            best = (mark_rank(mask), mask, os_slug(source, icon))
            log.info("The OS icon for %s is a CANDIDATE: %s (%d B, %s, gate "
                     "%.3f >= %.3f, rank %.3f)", app_name, source or "<no path>",
                     len(icon), conversion, score, icon_binarise.MIN_SCORE,
                     best[0][1])
        # ⚠️ INFO, not debug, and it names every number. "The icon does not
        # survive 1-bit" is true and useless: the questions a round of hardware
        # testing actually asks are WHICH file was read, what it scored and
        # against what -- and answering them cost a session of guessing before
        # this line existed. It runs once per application, not per tick.
        # ⚠️ THREE decimals. At two, a near miss printed "score 0.30 < 0.30"
        # -- a line that reads as a contradiction and sends the reader looking
        # for a comparison bug. Measured on GNOME Calculator, which lands just
        # under the gate.
        log.info("The OS icon for %s does not survive 1-bit: %s (%d B, %s, "
                 "score %.3f < %.3f) -- falling through to the catalog",
                 app_name, source or "<no path>", len(icon),
                 conversion or "nothing rendered", score,
                 icon_binarise.MIN_SCORE)

    # ⚠️ EVERY candidate is resolved and the BEST-SCORING one wins -- this is
    # not first-match-wins any more. A fixed source preference cannot express
    # the case it was changed for, and the per-app table that could is what
    # `docs/generic-icons-plan.md` exists to refuse:
    #
    #   * GNOME Terminal reports the display name "Terminal" and the exe stem
    #     `gnometerminal`. `si:gnometerminal` exists -- a heavy white plate,
    #     1134 px of ink, 0.362 -- so first-match shipped it and the far more
    #     legible `poly:terminal` (340 px, 0.415) was never reached.
    #
    # Ranking costs nothing per window switch: `app_icon_fetcher` resolves an
    # app ONCE per process, on its own thread, and caches the misses too.
    #
    # ⚠️ IT DOES NOT FIX SAFARI, and the reason is a gap in `score()` rather
    # than in the ordering here. `si:safari` is a near-solid disc with a
    # hairline needle and reads badly on the panel, but it scores 0.610 against
    # `mdi:apple-safari`'s 0.532 and therefore still wins. Its tight-bbox
    # density is 0.727, just over `MAX_LIT`, so `score()` takes its
    # polarity-inversion path and rates the INVERSE -- the path added for a
    # white `>_` knocked out of a black terminal plate. That path is gated on
    # an enclosed hole precisely to stop a filled silhouette being read as line
    # art (its comment records a flat disc scoring 0.43 that way), and the
    # needle IS an enclosed hole (share 0.188), so a mostly-filled disc with a
    # small hole walks through a gate built to catch a disc with none. The
    # separating term is that a real dark plate's inverse does not touch the
    # bounding box border while a silhouette's inverse is the page around it
    # and does -- untried, because `score()` is fitted to a judged 87-icon
    # corpus and a new term has to be validated against it, not against one
    # favourite mark. ⚠️ Do not "fix" this by reordering SOURCES: that is the
    # fixed preference this block replaced, and it would take GNOME Terminal
    # back with it.
    tried = candidates(app_name, names)
    reasons: dict = {}
    for name in tried:
        path = fetch_icon(name, cache_dir, allow_network, reasons=reasons)
        if not path:
            continue
        mask = render_mark(path)
        if mask is None:
            continue
        value = mark_rank(mask)
        if best is None or value > best[0]:
            best = (value, mask, name)
    if best is not None:
        log.info("Program mark for %s: %s (rank %.3f%s, best of %s)",
                 app_name, best[2], best[0][1],
                 "" if best[0][0] else ", read INVERTED",
                 ", ".join((["the OS icon"] if icon else []) + tried))
        return best[1], best[2]
    # The names are the whole story when nothing draws -- they say whether the
    # OS gave us a usable display name or only an executable stem.
    log.info("No program mark for %s: the catalog carries none of %s "
             "(OS names: %s)", app_name,
             ", ".join("%s [%s]" % (n, reasons.get(n, "did not render"))
                       for n in tried) or "<no candidates>",
             ", ".join(names) or "<none>")
    return None, (tried[0] if tried else None)
