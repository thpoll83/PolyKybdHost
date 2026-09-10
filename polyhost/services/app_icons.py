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

Simple Icons is still tried FIRST: it is the real brand mark where it exists,
and mdi's version is an interpretation of it. Adobe stays mostly uncovered (mdi
has `adobe` and `adobe-acrobat` and nothing else), and the route that would close
the remainder is the OS's OWN icon for the running process (the exe's resource
icon on Windows, the `.desktop`/hicolor theme on Linux, the bundle's `.icns` on
macOS) -- always exact, no catalog, and a per-platform lift nobody has taken yet.

Geometry: the mark occupies the RIGHT-HAND 40x40 SQUARE of the panel and the
left 32 px stay the legend's. That 40 is arithmetic, not taste. ESC (U+238B) inks
x 2..27, and `copy_overlay_to_buffer` clears a Chebyshev-3 courtyard around the
overlay's ink before drawing it -- so the icon's ink must start at x >= 31 for
the clear to begin at 28, one column past the glyph. 72 - 31 = 41, i.e. 40.
Measured over 36 marks: at 40 all 36 leave ESC untouched, at 44 only 20 do.
"""

from __future__ import annotations

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

# ⚠️ The prefixed mdi guesses are what reach Office at all -- an executable named
# `word` has to become `microsoft-word`. They are safe because of what is IN the
# prefix, measured rather than assumed: all 50 `microsoft-*` stems in mdi are
# genuine Microsoft product names (word, excel, teams, edge, azure, xbox, ...),
# and `adobe-*` has exactly one (`acrobat`). The only two stems that are also
# Simple Icons slugs -- `dot-net` and `github` -- are resolved by Simple Icons
# first and never reach this list. Re-run that check before adding a prefix.
MDI_PREFIXES = ("microsoft-", "adobe-")

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
# above). Not a setting: a bigger box eats the ESC glyph, and a smaller one
# wastes panel on the only keycap whose legend nothing else competes for.
PROGRAM_ICON_BOX = 40

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

    Three reductions before that, each measured against the shipped mapping's
    own app names rather than invented:

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


def candidates(app_name: str, mapping: dict | None = None) -> list:
    """Qualified `source:name` icons to try, in order, for one application.

    Empty when the app is suppressed or unnameable. The list is a preference
    order, not a set of equals: Simple Icons carries the real brand mark where it
    has one, so it is asked first and mdi only fills what it refuses.
    """
    if not app_name:
        return []
    mapping = load_slug_map() if mapping is None else mapping
    key = app_name.strip().lower()
    for probe in (key, normalise(app_name)):
        if probe in mapping:
            value = mapping[probe]
            return [] if value is None else [qualify(value)]
    out = []
    guess = normalise(app_name)
    if guess:
        out.append(f"si:{guess}")
    stem = kebab(app_name)
    if stem:
        # ⚠️ The BARE mdi stem is deliberately NOT tried. mdi is 7400 icons of
        # which most are generic UI symbols, so a bare hit is not evidence of a
        # brand: `code` resolves to a generic `</>` glyph, which on VS Code is a
        # wrong icon by this module's own rule. Measured, it would gain four apps
        # on a 151-app list and one of the four would be wrong. The prefixed
        # forms carry no such risk (every stem behind them is a product name),
        # and the handful of real brands mdi holds under a bare name get an
        # explicit map entry instead -- curated, and unable to go stale into
        # something wrong.
        out += [f"mdi:{prefix}{stem}" for prefix in MDI_PREFIXES]
    return out


def qualify(name: str) -> str:
    """`source:name`, defaulting an unqualified value to Simple Icons.

    Lets one map entry name either catalog -- `chrome: googlechrome` and
    `winword: mdi:microsoft-word` -- without a second file or a second column.
    """
    return name if ":" in name else f"{DEFAULT_SOURCE}:{name}"


def split_name(qualified: str) -> tuple:
    source, _, name = qualify(qualified).partition(":")
    return source, name


def slug_map_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "res", "app_icons.yaml")


def load_slug_map(path: str | None = None) -> dict:
    """app name -> slug, or -> None for "never guess for this one".

    Returns {} rather than raising: a broken map must cost the icons, never the
    overlay send that asks for them.
    """
    try:
        import yaml
        with open(path or slug_map_path(), encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception:
        return {}
    out = {}
    for key, value in data.items():
        for part in str(key).split(","):
            part = part.strip().lower()
            if part:
                out[part] = None if value is None else str(value).strip().lower()
    return out


def slug_for(app_name: str, mapping: dict | None = None) -> str | None:
    """The catalog slug for an application, or None to draw no icon.

    ⚠️ NO FUZZY MATCHING, here or anywhere downstream. A slug is an exact
    identifier and a *wrong* logo is worse than a missing one -- Krita on a KiCad
    window is a bug the user cannot explain, while an absent icon is self-evident
    and lands in the curation file. The explicit map wins; otherwise the guess
    above is offered and the catalog's own 404 is what rejects it.
    """
    if not app_name:
        return None
    mapping = load_slug_map() if mapping is None else mapping
    key = app_name.strip().lower()
    if key in mapping:
        return mapping[key]                     # may be None: suppressed
    guess = normalise(app_name)
    if guess in mapping:
        return mapping[guess]
    return guess or None


def _is_svg(data: bytes) -> bool:
    """Refuse anything that is not an SVG document.

    Same discipline as `icon_catalog._is_ttf` and `font_downloader`'s sfnt check:
    a proxy error page returning 200 would otherwise be cached under the mark's
    name and fail at render time, where the cause is invisible.
    """
    head = data[:512].lstrip()
    return head.startswith(b"<?xml") or head.startswith(b"<svg")


def icon_path(slug: str, cache_dir: str | None = None) -> str:
    """⚠️ The cache filename carries the SOURCE. The two catalogs share names
    (`mdi:slack` and `si:slack` are different drawings of the same brand), so a
    bare name would let whichever was fetched first answer for both."""
    source, name = split_name(slug)
    return os.path.join(cache_dir or default_cache_dir(), f"{source}-{name}.svg")


def fetch_icon(slug: str, cache_dir: str | None = None,
               allow_network: bool | None = None) -> str | None:
    """Path to the mark's SVG, downloading it once if needed.

    Returns None when it is neither cached nor reachable -- and when the catalog
    simply does not carry it, which is an ordinary 404 rather than a fault. The
    caller then draws nothing, so nothing here raises.
    """
    if not slug:
        return None
    source, name = split_name(slug)
    if source not in SOURCES:
        # Checked BEFORE the cache, not after: otherwise a file left under an
        # unknown source (a stale name, a hand-dropped file) is served as if the
        # source were real, and the one function that decides what may be fetched
        # answers from disk instead.
        return None
    path = icon_path(slug, cache_dir)
    if os.path.exists(path) and os.path.getsize(path) > 16:
        return path
    if not (auto_fetch_enabled() if allow_network is None else allow_network):
        return None
    url = SOURCES[source].format(name=name)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        log.debug("No catalog mark for '%s' (HTTP %s)", slug, exc.code)
        return None
    except Exception as exc:
        log.debug("Could not fetch the mark for '%s': %s", slug, exc)
        return None
    if not _is_svg(data):
        return None
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".part"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)       # never leave a half file under the real name
    except OSError:
        return None
    return path


def title_of(svg_path: str) -> str | None:
    """The brand name the catalog gives this mark, from the SVG's own <title>.

    Worth logging beside the slug: it is the only thing that would show a guess
    having landed on the wrong brand, which is the failure `slug_for` refuses to
    risk and cannot detect by itself.
    """
    try:
        with open(svg_path, encoding="utf-8") as fh:
            head = fh.read(2048)
    except OSError:
        return None
    match = re.search(r"<title>(.*?)</title>", head, re.S)
    return match.group(1).strip() if match else None


def render_overlay(svg_path: str, box: int = PROGRAM_ICON_BOX):
    """A 40x72 boolean array with the mark right-aligned, everything else blank.

    That shape is what OverlayData consumes, so the result rides the existing
    overlay transport with no firmware change -- and because the left two thirds
    are blank, the ROI is small and the compressed payload well under a frame.
    """
    try:
        import io
        import cairosvg
        import numpy as np
        from PIL import Image
    except Exception:
        # cairosvg is the one dependency this feature adds. A broken install
        # must cost the icon, never the overlay.
        log.debug("Cannot render a program icon: cairosvg/Pillow unavailable")
        return None
    try:
        with open(svg_path, "rb") as fh:
            data = fh.read()
        png = cairosvg.svg2png(bytestring=data,
                               output_width=box * SUPERSAMPLE,
                               output_height=box * SUPERSAMPLE)
        alpha = np.array(Image.open(io.BytesIO(png)).convert("RGBA"))[..., 3]
    except Exception as exc:
        log.debug("Could not rasterise %s: %s", svg_path, exc)
        return None

    rows = (alpha > 0).any(1).nonzero()[0]
    cols = (alpha > 0).any(0).nonzero()[0]
    if not len(rows) or not len(cols):
        return None
    from PIL import Image
    import numpy as np
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


def program_overlay(app_name: str, mapping: dict | None = None,
                    cache_dir: str | None = None,
                    allow_network: bool | None = None):
    """(mask, qualified name) for the focused app, or (None, first candidate).

    A name comes back either way so the caller can say which app it failed for --
    an unresolvable name and a resolvable one no catalog carries want different
    curation entries.
    """
    for name in candidates(app_name, mapping):
        path = fetch_icon(name, cache_dir, allow_network)
        if not path:
            continue
        mask = render_overlay(path)
        if mask is not None:
            return mask, name
    first = candidates(app_name, mapping)
    return None, (first[0] if first else None)
