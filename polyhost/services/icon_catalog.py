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
import urllib.parse
import urllib.request

CSS_ENDPOINT = "https://fonts.googleapis.com/css2"
FAMILY = "Material Symbols Outlined"
CODEPOINTS_URL = (
    "https://raw.githubusercontent.com/google/material-design-icons/master/"
    "variablefont/MaterialSymbolsOutlined%5BFILL%2CGRAD%2Copsz%2Cwght%5D.codepoints"
)

# ⚠️ The User-Agent decides the FORMAT Google serves. A modern browser UA gets
# woff2, which Pillow cannot open; an absent or old one gets plain TTF. Asking
# for TTF is the whole reason this needs no rasteriser dependency, so the UA is
# load-bearing rather than politeness -- and `_is_ttf` below refuses anything
# else rather than caching a file that will fail at render time.
TTF_USER_AGENT = "Mozilla/5.0"

HTTP_TIMEOUT = 15

# Where the icon sits in the 72x40 keycap. LOWER_LEFT is the default: one fixed
# corner the eye learns, and the two right-hand corners are already spoken for --
# the firmware draws the Shift preview upper-right and the AltGr hint lower-right.
PLACEMENTS = ("lower_left", "lower_right", "upper_left", "upper_right", "right")
DEFAULT_PLACEMENT = "lower_left"

# ⚠️ THE LOWER-LEFT CORNER IS THE CONTESTED ONE, not the free one. The base
# legend is LEFT-aligned from x~0 and descends below the baseline, so it comes
# straight down into that corner. Measured through the shipped renderer
# (tools/oled_preview.py against res/preview/, origin x=28 baseline=23):
#
#   plain legend   S B W M Q @    ink x 0..24, y 1..25
#   with descender g y j p q      ink x 0..14, y 0..27
#
# then pixel against pixel, all 47 lexicon icons from one subset versus each of
# those letters, in the lower-left corner:
#
#   height   clashing pairs (plain)   worst   clashing (descender)   worst
#     12          0 / 282               0 px        4 / 235           3 px
#     14          0 / 282               0 px       83 / 235          10 px
#     16          8 / 282               2 px      169 / 235          23 px
#     18         22 / 282               7 px      183 / 235          22 px
#     20        153 / 282              22 px      191 / 235          35 px
#
# 14 is the largest height that NEVER touches a plain legend; 16 costs eight
# pairs two pixels each; 20 is the cliff. 16 ships because it is the smallest
# size at which an icon is reliably identifiable -- rendered side by side,
# `search` at 12 is a dot with a tail and `zoom_in` a smudge, while at 16 all
# nine sampled icons read at a glance. Set 14 for a strictly clean plain legend.
#
# ⚠️ NO useful lower-left height avoids a DESCENDER. 12 nearly does (4 pairs, 3
# px) and is unreadable; every legible size clips g/y/j/p/q. That is accepted
# rather than solved: the icon appears while a modifier is held, where the
# shortcut is what the eye is on, and a nicked tail costs less than an icon
# nobody can identify.
#
# The three RIGHT-hand placements are clash-free with the base legend at EVERY
# size measured -- 0 / 282 and 0 / 235 throughout, because the legend ends near
# x=24 and they grow leftward from x=70. Their cost is the other direction: that
# is where the firmware draws the Shift preview (upper right) and the AltGr hint
# (lower right). upper_left is the one placement with no case at all: 279 of 282
# plain pairs clash even at 12 px, worst 30, because it lands on the legend's
# own cap height.
DEFAULT_ICON_HEIGHT = 16
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
    """
    right = PANEL_W - width - margin
    bottom = PANEL_H - height - margin
    return {
        "lower_left": (margin, bottom),
        "lower_right": (right, bottom),
        "upper_left": (margin, margin),
        "upper_right": (right, margin),
        "right": (right, (PANEL_H - height) // 2),
    }.get(placement, (margin, bottom))


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


def codepoints_path(cache_dir: str | None = None) -> str:
    return os.path.join(cache_dir or default_cache_dir(), "codepoints.txt")


def load_codepoints(cache_dir: str | None = None,
                    allow_network: bool = True) -> dict[str, int]:
    """name -> codepoint for every icon in the catalog, cached on disk.

    Rendering goes by codepoint rather than by the font's name ligatures,
    because ligature substitution needs Raqm in Pillow and is not guaranteed to
    be compiled in. A codepoint always draws.
    """
    path = codepoints_path(cache_dir)
    text = ""
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            text = ""
    if not text and allow_network:
        try:
            text = _get(CODEPOINTS_URL).decode("utf-8", "replace")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        except Exception:
            return {}
    out: dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            try:
                out[parts[0]] = int(parts[1], 16)
            except ValueError:
                continue
    return out


def subset_path(names, cache_dir: str | None = None) -> str:
    """Cache file for one SET of icon names.

    Keyed on the sorted set, so growing the lexicon fetches a new subset and
    leaves the old one cached rather than invalidating anything.
    """
    key = hashlib.sha256(",".join(sorted(set(names))).encode()).hexdigest()[:16]
    return os.path.join(cache_dir or default_cache_dir(), f"symbols-{key}.ttf")


def fetch_subset(names, cache_dir: str | None = None,
                 allow_network: bool = True) -> str | None:
    """Path to a TTF containing exactly `names`, downloading it once if needed.

    Returns None when it is neither cached nor reachable -- the caller then draws
    the label text, which is why nothing here raises.
    """
    names = sorted(set(n for n in names if n))
    if not names:
        return None
    path = subset_path(names, cache_dir)
    if os.path.exists(path) and os.path.getsize(path) > 4:
        return path
    if not allow_network:
        return None
    try:
        query = urllib.parse.urlencode({"family": FAMILY.replace(" ", "+"),
                                        "icon_names": ",".join(names)},
                                       safe="+,")
        css = _get(f"{CSS_ENDPOINT}?{query}", TTF_USER_AGENT).decode("utf-8", "replace")
        start = css.find("url(")
        if start < 0:
            return None
        url = css[start + 4:css.find(")", start)].strip("'\" ")
        data = _get(url, TTF_USER_AGENT)
        if not _is_ttf(data):
            return None
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".part"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)          # never leave a half file under the real name
        return path
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
