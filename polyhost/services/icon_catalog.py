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

⚠️ THE ICON IS RIGHT-ALIGNED AND THE REST OF THE FRAME IS BLANK, deliberately.
The firmware's `copy_overlay_to_buffer` clears a courtyard around the overlay's
ink and then draws it, so blank areas leave the legend underneath intact -- the
letter stays on the left and the icon punches in on the right. The host
therefore never needs to know what the legend says. A full-frame icon would
erase it.

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

# Icon height in the 72x40 keycap, in pixels. Rendered and compared at 24/28/32/
# 36/40: collision with the legend is zero at EVERY size (right-aligning grows the
# icon leftward from x=70, and a letter ends near x=23), so the constraint is not
# overlap but balance -- at 40 the icon is flush against the panel edge, and at 24
# `format_bold` reads as a small B beside the legend's big B. 28-32 keeps a margin
# on all sides with the letter still dominant.
DEFAULT_ICON_HEIGHT = 30
MIN_ICON_HEIGHT, MAX_ICON_HEIGHT = 12, 40

PANEL_W, PANEL_H = 72, 40
ICON_MARGIN = 2

_TTF_MAGIC = (b"\x00\x01\x00\x00", b"true", b"ttcf")


def icon_height() -> int:
    """The configured keycap icon height, clamped to what the panel can hold."""
    try:
        from polyhost.settings import read_setting
        value = int(read_setting("shortcut_icon_height", DEFAULT_ICON_HEIGHT))
    except Exception:
        value = DEFAULT_ICON_HEIGHT
    return max(MIN_ICON_HEIGHT, min(MAX_ICON_HEIGHT, value))


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


def render_overlay(name: str, font_path: str, codepoints: dict[str, int],
                   height: int | None = None, margin: int = ICON_MARGIN):
    """A 40x72 boolean array with the icon right-aligned, everything else blank.

    That shape is what OverlayData consumes, so the result goes straight down the
    existing overlay transport -- and because most of the frame is blank, its ROI
    is small and the compressed payload is far under the 360-byte full frame.
    """
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    cp = codepoints.get(name)
    if cp is None:
        return None
    height = icon_height() if height is None else height
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
        return None                     # the subset does not carry this glyph
    draw.text((PANEL_W - width - margin - box[0], (PANEL_H - tall) // 2 - box[1]),
              glyph, font=font, fill=255)
    return np.array(image) > 96
