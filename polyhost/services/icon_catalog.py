"""Fetch UI icons from an online catalog on demand, cache them, render keycaps.

The generic half of the shortcut-icon feature. `shortcut_icons` decides that a
label called "Save" means the concept `save`; this turns a concept into pixels
the keyboard can draw, for ANY icon in the catalog, without shipping a font.

Why this rather than the font pack: a glyph in a `.plyf` bundle has to be chosen
in advance, built with the pinned fontconvert, and reshipped with a
content_version bump. That is the wall the Bold/Italic/Underline case hit --
the letterforms existed, just not in a bundle. Fetching on demand removes the
wall entirely, and needs NO firmware change at all: the result is an ordinary
overlay, which the existing transport already carries.

⚠️ THE ICON OCCUPIES ONE CORNER AND THE REST OF THE FRAME IS BLANK, deliberately.
The firmware's `copy_overlay_to_buffer` clears a courtyard around the overlay's
ink and then draws it, so blank areas leave the legend underneath intact -- the
legend survives and the icon punches in beside it. The host therefore never needs
to know what the legend says. A full-frame icon would erase it.

Catalog: Google Material Symbols (Apache-2.0), which this repo already uses for
its tray icons, so the naming vocabulary is one the project has committed to.

⚠️ Requested as a SERVER-SIDE SUBSET, not the whole font. Measured: the full
variable font is 10.6 MB, while `icon_names=` returns 4.8 KB for twelve icons --
a ratio that decides it, since a user mapping eight icons in Word should not pay
ten megabytes. Both render pixel-identically.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import urllib.parse
import urllib.request

CSS_ENDPOINT = "https://fonts.googleapis.com/css2"
FAMILY = "Material Symbols Outlined"

#: The `wght` axis Material Symbols is fetched at. The default is 400 and it is
#: visibly heavier than Fluent beside it: measured over eight concepts both
#: catalogs carry, at the shipped 36 px 1-bit render, Material inks **1.30x**
#: Fluent at 400 and **0.85x** at 300. The two faces are mixed on one keycap row
#: -- a menu bar draws four side by side -- so that difference reads as a
#: different stroke weight rather than as a different icon set.
#:
#: WARNING: THE ENDPOINT QUANTISES to the named instances, so this is not a free
#: dial. Measured: 200 and 250 return a BYTE-IDENTICAL font, as do 300 and 350.
#: Only 200 / 300 / 400 are reachable here. That matters because the overlay
#: generator prescribes "250-300" for Material
#: (`res/overlay_sources/material_symbols.py`, which renders the variable font
#: locally and really can hit 250) -- asking for 250 through THIS path silently
#: gets you 200, which that same note calls "too thin to survive the 1-bit/40 px
#: downscale". 300 is the only served instance between the two.
MATERIAL_WEIGHT = 300

#: `opsz,wght,FILL,GRAD` in that order -- the CSS2 API wants registered (lower
#: case) axes first, then custom ones, each alphabetically, and rejects any
#: other ordering.
MATERIAL_AXES = "opsz,wght,FILL,GRAD@24,{wght},0,0"
CODEPOINTS_URL = (
    "https://raw.githubusercontent.com/google/material-design-icons/master/"
    "variablefont/MaterialSymbolsOutlined%5BFILL%2CGRAD%2Copsz%2Cwght%5D.codepoints"
)

# --- faces -----------------------------------------------------------------
#
# Two catalogs, named like `app_icons`'s `si:`/`mdi:` for the same reason: a
# qualified `face:name` is one string a lexicon entry can carry, so the choice
# travels with the concept instead of living in a parallel table.
#
# ⚠️ THE TWO ARE NOT INTERCHANGEABLE BY NAME. Fluent's vocabulary is
# systematically its own -- `undo` is `arrow_undo`, `close` is `dismiss`, `paste`
# is `clipboard_paste`, `bold` is `text_bold`, `fullscreen` is `arrow_maximize`,
# `quit` is `sign_out`. Measured over the 48 lexicon concepts, only 20 derive
# from the Material spelling, and a substring search invents false friends:
# `fireplace` for "replace", `briefcase` for "change case", `arrow_clockwise`
# for "lock". So each concept names its Fluent icon explicitly; there is no
# derivation to be clever with.
#
# ⚠️ FLUENT HAS NO SERVER-SIDE SUBSET. Google serves `icon_names=` and returns
# 4.8 KB for twelve icons; Fluent ships one 2.8 MB TTF on GitHub and nothing
# else, so the whole font is fetched once and cached. That is 3.8x smaller than
# the 10.6 MB full Material font this module already rejected for the same
# reason, and it is paid once per machine rather than per icon set -- but it is
# the cost, and it is why `fetch_subset` branches per face rather than
# pretending the two behave alike.
MATERIAL, FLUENT = "material", "fluent"
FACES = (FLUENT, MATERIAL)
DEFAULT_FACE = MATERIAL

# ⚠️ PINNED TO A COMMIT, not to `main`, and that pin is load-bearing twice over.
#
# The hand-made template overlays are generated from this same font and
# COMMITTED as PNGs, so their pixels are frozen at whatever Fluent shipped the
# day they were generated. If the app fetched `main`, an upstream redraw would
# silently move the generic path off the templates and every shared pool slot
# would split in two -- the byte dedupe is exact, so a one-pixel change is a
# full miss. The two halves have to read the same bytes or they are not one
# icon set.
#
# It also restores the generator's contract, which is that re-running it on the
# committed `bindings.yaml` reproduces the overlays byte for byte. A moving
# branch makes that depend on the day.
#
# A commit rather than a tag because a tag can be moved and this one cannot.
# Bumping it is a deliberate act: change the pin, re-run
# `generate_app_overlays.py` for every template, and check what moved -- the
# same shape as `app_icons.CDN_VERSION` and as the font pack's content_version.
FLUENT_REF = "9cf8af0f95a555918a60b8147a2f33a6a1248442"
FLUENT_RAW = ("https://raw.githubusercontent.com/microsoft/fluentui-system-icons/"
              f"{FLUENT_REF}/fonts/FluentSystemIcons-Regular")
FLUENT_CODEPOINTS_URL = f"{FLUENT_RAW}.json"
FLUENT_FONT_URL = f"{FLUENT_RAW}.ttf"
# The table keys every size and weight it ships; 24/regular is the one drawn
# here, and is also the set the hand-made template overlays are sourced from.
FLUENT_PREFIX, FLUENT_SUFFIX = "ic_fluent_", "_24_regular"


def split_face(name: str) -> tuple[str, str]:
    """`fluent:copy` -> ("fluent", "copy"); a bare name takes DEFAULT_FACE.

    Mirrors `app_icons.qualify`, so an unqualified entry keeps working and a
    qualified one pins its catalog.
    """
    text = str(name or "")
    face, sep, rest = text.partition(":")
    if sep and face in FACES:
        return face, rest
    return DEFAULT_FACE, text

# ⚠️ The User-Agent decides the FORMAT Google serves. A modern browser UA gets
# woff2, which Pillow cannot open; an absent or old one gets plain TTF. Asking
# for TTF is the whole reason this needs no rasteriser dependency, so the UA is
# load-bearing rather than politeness -- and `_is_ttf` below refuses anything
# else rather than caching a file that will fail at render time.
TTF_USER_AGENT = "Mozilla/5.0"

HTTP_TIMEOUT = 15

# Where the icon sits in the 72x40 keycap. LOWER_RIGHT is the default, because
# that is the CONVENTION EVERY HAND-MADE TEMPLATE ALREADY FOLLOWS -- all twelve
# `overlay_sources/*/bindings.yaml` set `anchor: bottom-right`, so any other
# corner makes a generic app look different from a templated one on the same
# board. That inconsistency is the same defect E3 removed for the program mark,
# where one keycap behaved two ways depending on whether somebody had drawn
# overlays for that application.
#
# ⚠️ It was LOWER_LEFT until a hardware report, on the reasoning that the two
# right-hand corners are "already spoken for" -- the firmware draws the Shift
# preview upper-right and the AltGr hint lower-right. That is true and it is the
# weaker half of the trade, for two reasons this file can measure:
#   * the BASE LEGEND inks columns 0..24 (pinned as `LEGEND_RIGHT` in the
#     tests), so a left-hand icon covers the legend on EVERY key while the
#     right-hand one clears it entirely;
#   * the AltGr hint exists only on the keys and layouts that bind one, and only
#     in the unshifted view, where the legend is always there.
# The courtyard means neither can merge with what is underneath (see below), so
# what is being traded is which pixels get covered, not legibility.
PLACEMENTS = ("lower_left", "lower_right", "upper_left", "upper_right", "right")
DEFAULT_PLACEMENT = "lower_right"

# ⚠️ AN OVERLAP IS NOT A COLLISION -- the firmware CLEARS A COURTYARD around the
# overlay's ink before drawing it, so the icon always lands on cleared black and
# can never merge with the letter underneath. `copy_overlay_to_buffer` calls
# `kdisp_clear_rowmajor_courtyard(..., KDISP_CY_DEFAULT)`, a Chebyshev-3 dilation
# of the overlay mask (per horizontal run: +-3 rows, +-3 columns).
#
# So the cost of a bigger icon is not muddle, it is legend PIXELS EATEN -- and it
# starts before any ink overlaps, because the 3 px halo is cleared regardless.
# Measured over all 47 lexicon icons x 17 letters, lower-left, with the courtyard
# modelled (legend pixels still lit after the clear):
#
#   height   legend kept (median)   worst   icon ink
#     16            100 %            68 %      55 px
#     24             66 %            36 %     120 px
#     28             57 %            23 %     168 px
#     32             42 %             0 %     220 px
#     36             33 %             0 %     293 px
#     40             35 %             0 %     339 px
#
# 32 ships: the icon is unambiguous at a glance (four times the ink of 16) and
# about half the legend survives beside it. Losing the rest is the intended
# trade, not damage -- the overlay is only on screen while a modifier is HELD,
# where the shortcut is what the eye is on and the letter is already known. Set a
# smaller height for a legend-first keycap; 16 leaves it untouched.
#
# For reference, raw ink-on-ink overlap in the lower-left corner (what a reader
# might expect to matter, and what the courtyard makes cosmetic): 0 / 282 pairs
# against a plain legend at 12 and 14 px, 8 at 16, 153 at 20. The legend itself
# inks x 0..24, y 1..25 (S B W M Q @) and y 0..27 with a descender (g y j p q),
# measured through tools/oled_preview.py against res/preview/.
#
# The three RIGHT-hand placements never touch the legend at any size -- it ends
# near x=24 and they grow leftward from x=70 -- but they are where the firmware
# draws the Shift preview (upper right) and the AltGr hint (lower right).
# upper_left has no case at all: it lands on the legend's own cap height.
# 36, not 40, and the four px are the whole point: at 40 the nominal box IS the
# panel height, so `place()` clamps and the top margin disappears -- the silent
# clip its own docstring warns about. Measured over eight shipped concepts at
# 36: real ink 26-30 px tall, left edge at column 37, margins intact on every
# side. 32 was the earlier default and reads small beside the firmware legend.
# 38 and 40 stay reachable through `shortcut_icon_height` for anyone who wants
# them.
DEFAULT_ICON_HEIGHT = 36
MIN_ICON_HEIGHT, MAX_ICON_HEIGHT = 8, 40

PANEL_W, PANEL_H = 72, 40
ICON_MARGIN = 1

_TTF_MAGIC = (b"\x00\x01\x00\x00", b"true", b"ttcf")


def icon_height() -> int:
    """The configured keycap icon height, clamped to what the panel can hold."""
    try:
        from polyhost.settings import read_setting
        value = int(read_setting("shortcut_icon_height", DEFAULT_ICON_HEIGHT))
    except Exception:
        value = DEFAULT_ICON_HEIGHT
    return max(MIN_ICON_HEIGHT, min(MAX_ICON_HEIGHT, value))


def icon_placement() -> str:
    """The configured corner, falling back to the default for an unknown value."""
    try:
        from polyhost.settings import read_setting
        value = str(read_setting("shortcut_icon_placement", DEFAULT_PLACEMENT))
    except Exception:
        value = DEFAULT_PLACEMENT
    return value if value in PLACEMENTS else DEFAULT_PLACEMENT


def place(width: int, height: int, placement: str,
          margin: int = ICON_MARGIN) -> tuple[int, int]:
    """Top-left corner for an icon of this size, in panel coordinates.

    Pure, so the geometry is testable without a font or a network.

    ⚠️ CLAMPED, because the margin does not fit at every size: an icon inking
    the full MAX_ICON_HEIGHT of 40 leaves `PANEL_H - 40 - 1` = -1, and PIL then
    draws at a negative y and clips the top row in silence. Material glyphs ink
    a row or two under their nominal size so they only graze it, but an icon
    that fills its box -- an SVG mark rasterised to a square -- hits it exactly.
    Losing the margin on one side is the right answer there; losing a row of the
    artwork is not.
    """
    right = PANEL_W - width - margin
    bottom = PANEL_H - height - margin
    corners = {
        "lower_left": (margin, bottom),
        "lower_right": (right, bottom),
        "upper_left": (margin, margin),
        "upper_right": (right, margin),
        "right": (right, (PANEL_H - height) // 2),
    }
    # ⚠️ The fall-back is DERIVED from DEFAULT_PLACEMENT, never written out
    # again. It was a second copy of the same corner, which agreed by luck until
    # the default moved and then quietly disagreed with `icon_placement()` --
    # so an unknown value landed in one corner and a missing setting in another.
    # A test pins them equal; this is what makes that test unable to go stale.
    x, y = corners.get(placement, corners[DEFAULT_PLACEMENT])
    return max(0, min(x, PANEL_W - width)), max(0, min(y, PANEL_H - height))


def default_cache_dir() -> str:
    """Per-user cache for the fetched icon font, beside the Noto source cache."""
    try:
        import platformdirs
        base = platformdirs.user_cache_dir("PolyKybd", "PolyTasten")
    except Exception:
        base = os.path.join(os.path.expanduser("~"), ".cache", "PolyKybd")
    return os.path.join(base, "icons")


def _is_ttf(data: bytes) -> bool:
    """Refuse anything that is not a TrueType file.

    Same discipline as font_downloader's sfnt check, and for the same reason: a
    proxy error page, or Google deciding to serve woff2, would otherwise be
    cached under the font's name and fail much later at render time, where the
    cause is invisible.
    """
    return len(data) > 4 and data[:4] in _TTF_MAGIC


def _get(url: str, user_agent: str | None = None) -> bytes:
    request = urllib.request.Request(url)
    if user_agent:
        request.add_header("User-Agent", user_agent)
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        return response.read()


def codepoints_path(cache_dir: str | None = None,
                    face: str = DEFAULT_FACE) -> str:
    stem = "codepoints.txt" if face == MATERIAL else f"codepoints-{face}.json"
    return os.path.join(cache_dir or default_cache_dir(), stem)


def _cached_text(path: str, url: str, allow_network: bool) -> str:
    """The cached body for `url`, fetching and storing it once. "" on failure."""
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            pass
    if not allow_network:
        return ""
    try:
        text = _get(url).decode("utf-8", "replace")
    except Exception:
        return ""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError:
        pass                    # an uncacheable answer is still a usable one
    return text


def _fluent_codepoints(text: str) -> dict[str, int]:
    """Fluent's table -> {stem: codepoint} for the 24px regular set.

    ⚠️ Keyed on the STEM (`copy`), not the full `ic_fluent_copy_24_regular`, so a
    lexicon entry names the icon the way a person would and the size/weight this
    module draws stays one decision in one place.
    """
    import json
    try:
        raw = json.loads(text)
    except Exception:
        return {}
    out: dict[str, int] = {}
    for key, value in (raw or {}).items():
        if not (key.startswith(FLUENT_PREFIX) and key.endswith(FLUENT_SUFFIX)):
            continue
        try:
            out[key[len(FLUENT_PREFIX):-len(FLUENT_SUFFIX)]] = int(value)
        except (TypeError, ValueError):
            continue
    return out


def load_codepoints(cache_dir: str | None = None,
                    allow_network: bool = True,
                    face: str = DEFAULT_FACE) -> dict[str, int]:
    """name -> codepoint for every icon in the catalog, cached on disk.

    Rendering goes by codepoint rather than by the font's name ligatures,
    because ligature substitution needs Raqm in Pillow and is not guaranteed to
    be compiled in. A codepoint always draws.
    """
    url = CODEPOINTS_URL if face == MATERIAL else FLUENT_CODEPOINTS_URL
    text = _cached_text(codepoints_path(cache_dir, face), url, allow_network)
    if face == FLUENT:
        return _fluent_codepoints(text)
    out: dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            try:
                out[parts[0]] = int(parts[1], 16)
            except ValueError:
                continue
    return out


def subset_path(names, cache_dir: str | None = None,
                face: str = DEFAULT_FACE) -> str:
    """Cache file for one SET of icon names.

    Keyed on the sorted set, so growing the lexicon fetches a new subset and
    leaves the old one cached rather than invalidating anything.

    ⚠️ Fluent ignores `names`: there is no subset endpoint, so one whole-font
    file serves every set. The path is therefore stable rather than content-
    keyed, which is also what stops a growing lexicon re-downloading 2.8 MB.
    """
    if face == FLUENT:
        return os.path.join(cache_dir or default_cache_dir(), "fluent-regular.ttf")
    key = hashlib.sha256(",".join(sorted(set(names))).encode()).hexdigest()[:16]
    # WARNING: THE WEIGHT IS IN THE FILENAME, and it has to be: the cache is
    # keyed on what the file CONTAINS, not on what was asked for. Leave it out
    # and every machine that has already fetched a set keeps serving the old
    # weight for good -- a change to MATERIAL_WEIGHT would then be invisible to
    # exactly the users who have been running the feature, and visible only on a
    # fresh install. In the name rather than folded into the hash so a mismatch
    # is readable in the cache dir instead of being one opaque digest against
    # another.
    return os.path.join(cache_dir or default_cache_dir(),
                        f"symbols-w{MATERIAL_WEIGHT}-{key}.ttf")


def _store_font(path: str, data: bytes) -> str | None:
    """Write a fetched font, refusing anything that is not a TTF.

    ⚠️ **The temp name is unique per CALL, not `path + ".part"`.** Since E18 the
    overlay generator renders through this module too, so the generator and the
    running host really can fetch the Fluent font at the same moment -- and a
    shared name means each truncates the other's file, the second `os.replace`
    moves an incomplete TTF into the cache, and the first raises
    FileNotFoundError because its `.part` is already gone. Exactly what
    `PolySettings._save_merged` records one module over: "unique per SAVE, not
    per process".
    """
    if not _is_ttf(data):
        return None
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory,
                               prefix=os.path.basename(path) + ".", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)      # never leave a half file under the real name
    except OSError:
        # The cache is a convenience, so a failed write is not fatal -- but it
        # must not leave a stray `.part` behind for the next run to trip over.
        try:
            os.unlink(tmp)
        except OSError:
            # Already gone, or the directory is unwritable -- either way there
            # is nothing left to clean up and nothing a caller could do. The
            # ORIGINAL failure is what matters and it is reported by the None
            # below; raising this one instead would replace a "could not write
            # the font" with a "could not delete a temp file".
            pass
        return None
    return path


def _cached_ttf(path: str) -> str | None:
    """`path` if it holds a real TTF, else None.

    ⚠️ **The MAGIC, not just the size.** `_is_ttf` exists so a proxy error page
    or a woff2 cannot be cached under the font's name and "fail much later at
    render time, where the cause is invisible" -- and the cache check next door
    accepted anything over four bytes, which is the same reasoning with the
    opposite conclusion four lines apart. A cache corrupted once stayed broken
    for good, because nothing ever re-examined it. Refusing it here also
    self-heals a file an older build left behind: the caller falls through to
    the download.
    """
    try:
        with open(path, "rb") as fh:
            return path if _is_ttf(fh.read(8)) else None
    except OSError:
        return None


def fetch_subset(names, cache_dir: str | None = None,
                 allow_network: bool = True,
                 face: str = DEFAULT_FACE) -> str | None:
    """Path to a TTF that can draw `names`, downloading it once if needed.

    Returns None when it is neither cached nor reachable -- the caller then draws
    the label text, which is why nothing here raises.
    """
    names = sorted(set(n for n in names if n))
    if not names:
        return None
    path = subset_path(names, cache_dir, face)
    cached = _cached_ttf(path)
    if cached:
        return cached
    if not allow_network:
        return None
    if face == FLUENT:
        try:
            return _store_font(path, _get(FLUENT_FONT_URL, TTF_USER_AGENT))
        except Exception:
            return None
    try:
        family = f"{FAMILY}:{MATERIAL_AXES.format(wght=MATERIAL_WEIGHT)}"
        query = urllib.parse.urlencode({"family": family.replace(" ", "+"),
                                        "icon_names": ",".join(names)},
                                       safe="+,@")
        css = _get(f"{CSS_ENDPOINT}?{query}", TTF_USER_AGENT).decode("utf-8", "replace")
        start = css.find("url(")
        if start < 0:
            return None
        url = css[start + 4:css.find(")", start)].strip("'\" ")
        return _store_font(path, _get(url, TTF_USER_AGENT))
    except Exception:
        return None


_COVERAGE: dict[str, frozenset] = {}


def font_covers(font_path: str, codepoint: int) -> bool:
    """Is this codepoint really in the font, or would it draw `.notdef`?

    ⚠️ A MISSING GLYPH IS NOT BLANK -- it renders as `.notdef`, a filled box
    with a diagonal cross, which is worse than drawing nothing: it inks most of
    the corner, means nothing, and (unlike a blank frame) wipes the legend
    underneath it. The bbox test below cannot catch it, because `.notdef` has a
    perfectly good non-zero bounding box; the comment there used to claim it
    could. Found by rendering a contact sheet -- six of nine icons in it were
    boxes -- not by reading the code.

    Reachable in normal use: `icon_names=` is a request, and Google returns a
    subset of whatever it recognised, so one renamed or mistyped name comes back
    silently absent while every other icon in the same file is fine.

    fontTools is already a runtime dependency; the cmap is cached per file, so
    this costs one parse per subset rather than one per keycap.
    """
    try:
        have = _COVERAGE.get(font_path)
        if have is None:
            from fontTools.ttLib import TTFont
            with TTFont(font_path, lazy=True) as f:
                have = frozenset(f.getBestCmap())
            _COVERAGE[font_path] = have
    except Exception:
        return True     # unreadable: let the render try and fail on its own
    return codepoint in have


def render_overlay(name: str, font_path: str, codepoints: dict[str, int],
                   height: int | None = None, margin: int = ICON_MARGIN,
                   placement: str | None = None):
    """A 40x72 boolean array with the icon in ONE CORNER, everything else blank.

    That shape is what OverlayData consumes, so the result goes straight down the
    existing overlay transport -- and because most of the frame is blank, its ROI
    is small and the compressed payload is far under the 360-byte full frame.
    """
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    cp = codepoints.get(name)
    if cp is None:
        return None
    if not font_covers(font_path, cp):
        return None
    height = icon_height() if height is None else height
    placement = icon_placement() if placement is None else placement
    try:
        font = ImageFont.truetype(font_path, height)
    except Exception:
        return None
    glyph = chr(cp)
    image = Image.new("L", (PANEL_W, PANEL_H), 0)
    draw = ImageDraw.Draw(image)
    box = draw.textbbox((0, 0), glyph, font=font)
    width, tall = box[2] - box[0], box[3] - box[1]
    if width <= 0 or tall <= 0:
        return None                     # nothing to draw
    x, y = place(width, tall, placement, margin)
    draw.text((x - box[0], y - box[1]), glyph, font=font, fill=255)
    return np.array(image) > 96
