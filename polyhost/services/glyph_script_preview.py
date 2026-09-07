"""Draw what a glyph script would put on the keycaps — offline, from shipped data.

The glyph-script override (HID cmd 30) swaps the letter/digit legends for an
alternative script, and the scripts themselves ship with the host as the
``fantasy`` font-pack bundle (``polyhost/res/fontpack/fantasy.plyf``).  The
normal Latin face ships too, in the keycap-preview export
(``polyhost/res/preview/resident.plyf``).  So the host can draw every entry of
the tray's Keycap Script menu with no keyboard attached, no font pack flashed
and nothing downloaded — which is what turns a list of names into a list of
previews.

PIL only, no Qt: the Qt side is one conversion away in
``polyhost/gui/glyph_script_icon.py``.

⚠️ The codepoint arithmetic mirrors the firmware's ``glyph_script_codepoint()``
(``qmk_firmware/keyboards/polykybd/poly_keymap.c``): each script owns a dense
Private-Use block, letters ``a..z`` at ``base+0..25`` and — for the scripts that
have numerals — digits ``1..0`` at ``base+26..35``.  A script whose block is not
in the shipped pack simply has no preview; nothing here guesses.
"""
from __future__ import annotations

import logging

from polyhost.services import fontpack_bundle
from polyhost.services.fontpack_reader import decode_pack_file

# The per-script PUA blocks, from the firmware's `glyph_script_blocks[]`: Tengwar
# (GlyphScript value 1) at 0xE800, and one 0x40-wide block per script after it.
# A script's font is resolved by looking that base up in the pack rather than by
# position, so a pack that gains or reorders fonts yields NO preview for a script
# instead of a preview of the wrong one.
GLYPH_SCRIPT_PUA_BASE = 0xE800
GLYPH_SCRIPT_PUA_STRIDE = 0x40

LETTER_COUNT = 26          # a..z at base+0..25
DIGIT_FIRST_INDEX = 26     # '1'..'0' at base+26..35 (KC_1..KC_0 are contiguous)
DIGIT_COUNT = 10

# Where the two faces come from, and what a preview draws.
BUNDLE_FILE = "fantasy.plyf"
RESIDENT_PACK = "resident.plyf"     # the compiled-in fonts, from the preview export
SAMPLE_LETTERS = "abc"
SAMPLE_DIGITS = "123"

_log = logging.getLogger("polyhost.glyph_script_preview")


# ── Codepoints ───────────────────────────────────────────────────────────────

def script_base(script_value: int) -> int | None:
    """The PUA block base for a glyph-script value, or None for STANDARD (0),
    which has no block — it is the absence of an override."""
    if script_value is None or script_value < 1:
        return None
    return GLYPH_SCRIPT_PUA_BASE + (script_value - 1) * GLYPH_SCRIPT_PUA_STRIDE


def glyph_index(ch: str) -> int | None:
    """Dense index within a script's block for one sample character, mirroring the
    firmware's keycode arithmetic: 'a'..'z' -> 0..25, '1'..'9','0' -> 26..35."""
    if len(ch) != 1:
        return None
    if "a" <= ch <= "z":
        return ord(ch) - ord("a")
    if ch.isdigit():
        # KC_1..KC_0 are contiguous with 0 LAST, so '1'->26 ... '9'->34, '0'->35.
        return DIGIT_FIRST_INDEX + (int(ch) + 9) % 10
    return None


def script_codepoints(font, text: str) -> list:
    """The codepoints `text` draws as in this script — skipping any the font does
    not carry (a script with no numerals leaves the digit keys alone)."""
    out = []
    for ch in text:
        idx = glyph_index(ch)
        if idx is None:
            continue
        cp = font.first + idx
        if cp <= font.last:
            out.append(cp)
    return out


def has_digits(font) -> bool:
    """Whether this script covers the digit row.  The firmware carries a per-script
    `digits` flag; the font's own coverage is the observable form of it."""
    return font is not None and font.last >= font.first + DIGIT_FIRST_INDEX + DIGIT_COUNT - 1


def sample_text(font, letters: str = SAMPLE_LETTERS, digits: str = SAMPLE_DIGITS) -> str:
    """The characters a preview of this script should draw — the digits only when
    the script has numerals of its own."""
    return letters + (digits if has_digits(font) else "")


# ── Fonts ────────────────────────────────────────────────────────────────────

def font_for_script(pack, script_value: int):
    """The pack font that draws `script_value`, or None when the pack has no such
    block (an older bundle, or a script this release's pack predates)."""
    base = script_base(script_value)
    if base is None or pack is None:
        return None
    for font in pack.fonts:
        if font.first == base:
            return font
    return None


def latin_font(pack):
    """The face STANDARD draws with: the first font (in ALL_FONTS priority order)
    covering the ASCII letters, which is the front-to-back rule the firmware uses
    to pick a glyph.  None when the preview export is not shipped."""
    if pack is None:
        return None
    covering = [f for f in pack.fonts
                if f.first <= ord("a") and f.last >= ord("z")]
    if not covering:
        return None
    return min(covering, key=lambda f: f.global_index)


# ── Rasterising ──────────────────────────────────────────────────────────────

def ink_extent(font, cps) -> tuple:
    """(ymin, ymax) of the ink of every codepoint in `cps`, relative to the
    baseline (negative is above it).

    This is the vertical box a preview normalises against, and it is the reason a
    Braille cell reads as Braille: its 'a' is a single dot, so scaled to its OWN
    ink it would fill an icon as a solid square.  Measured against the whole
    alphabet the dot keeps its size and its place in the cell.  Returns (0, 0) for
    a set with no ink at all.
    """
    ymin, ymax = None, None
    for cp in cps:
        if not (font.first <= cp <= font.last):
            continue
        g = font.glyphs[cp - font.first]
        if g["width"] <= 0 or g["height"] <= 0:
            continue
        top = g["yOffset"]
        bottom = top + g["height"] - 1
        ymin = top if ymin is None else min(ymin, top)
        ymax = bottom if ymax is None else max(ymax, bottom)
    if ymin is None:
        return 0, 0
    return ymin, ymax


def layout_image(font, cps, extent_cps=None, gap: int = 1, fg: int = 255, bg: int = 0):
    """An 'L' image of `cps` laid out with the font's own advances.

    Height is the box of `extent_cps` (the alphabet by default), so every preview
    of one face is drawn at a single scale whatever sample it shows; width is the
    pen advance of the sample.  Returns None when nothing resolves to ink.
    """
    from PIL import Image

    cps = [cp for cp in cps if font.first <= cp <= font.last]
    if not cps:
        return None
    ymin, ymax = ink_extent(font, extent_cps if extent_cps is not None else cps)
    height = max(1, ymax - ymin + 1)
    baseline = -ymin                      # y of the baseline inside the canvas

    glyphs = [font.glyphs[cp - font.first] for cp in cps]
    width = sum(max(g["xAdvance"], g["width"] + g["xOffset"]) for g in glyphs)
    width += gap * (len(glyphs) - 1)
    if width <= 0:
        return None

    img = Image.new("L", (width, height), bg)
    px = img.load()
    bmp, n = font.bitmap, len(font.bitmap)
    pen = 0
    for i, g in enumerate(glyphs):
        if i:
            pen += gap
        w, h = g["width"], g["height"]
        bo = g["bitmapOffset"]
        cb = (h + 7) >> 3        # column-native (OLED page) bytes per column
        for xx in range(w):
            col = bo + xx * cb
            for yy in range(h):
                b = col + (yy >> 3)
                byte = bmp[b] if 0 <= b < n else 0
                if byte & (1 << (yy & 7)):
                    vx = pen + g["xOffset"] + xx
                    vy = baseline + g["yOffset"] + yy
                    if 0 <= vx < width and 0 <= vy < height:
                        px[vx, vy] = fg
        pen += max(g["xAdvance"], w + g["xOffset"])
    return img


# ── Loading the shipped data ─────────────────────────────────────────────────
# One decode per process (26 KB, well under a millisecond) behind an explicit
# cache: the menu asks for every script each time it builds its previews.  A
# missing or malformed file means a preview-less menu, never an error — the
# scripts themselves live on the keyboard and work regardless.

_pack_cache = {}   # str(path) -> Pack | None


def _load(path, hint: str):
    key = str(path)
    if key not in _pack_cache:
        pack = None
        try:
            pack = decode_pack_file(str(path), hint)
        except Exception as exc:                      # noqa: BLE001 - preview is optional
            _log.debug("No glyph-script previews from %s: %s", path, exc)
        _pack_cache[key] = pack
    return _pack_cache[key]


def load_pack(path=None):
    """The decoded `fantasy` bundle, or None when it is absent/unreadable."""
    return _load(path or (fontpack_bundle.res_dir() / BUNDLE_FILE), "fantasy")


def load_resident(path=None):
    """The decoded resident (compiled-in) fonts, or None when not shipped."""
    if path is None:
        path = fontpack_bundle.res_dir().parent / "preview" / RESIDENT_PACK
    return _load(path, "resident")


# ── The two entry points ─────────────────────────────────────────────────────

def script_preview(script_value: int, text: str = None):
    """Preview image for one glyph script (value >= 1), or None."""
    font = font_for_script(load_pack(), script_value)
    if font is None:
        return None
    cps = script_codepoints(font, text if text is not None else sample_text(font))
    letters = [font.first + i for i in range(LETTER_COUNT)]
    return layout_image(font, cps, extent_cps=letters)


def standard_preview(text: str = None):
    """Preview image for STANDARD — the normal Latin legends, drawn from the same
    resident face the keycaps use.  None when the preview export is not shipped."""
    font = latin_font(load_resident())
    if font is None:
        return None
    if text is None:
        text = SAMPLE_LETTERS + SAMPLE_DIGITS
    cps = [ord(ch) for ch in text if font.first <= ord(ch) <= font.last]
    letters = [ord(ch) for ch in "abcdefghijklmnopqrstuvwxyz"]
    return layout_image(font, cps, extent_cps=letters)


def preview(script_value: int, text: str = None):
    """Preview image for any GlyphScript value, STANDARD included, or None."""
    if not script_value:
        return standard_preview(text)
    return script_preview(script_value, text)
