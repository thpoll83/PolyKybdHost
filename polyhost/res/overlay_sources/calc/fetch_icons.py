#!/usr/bin/env python3
"""Fetch + render the Windows Calculator overlay icons (reproducible source step).

⚠️ THE SHORTCUT LIST IS NOT RESEARCH -- it is parsed from Calculator's OWN
RESOURCES. `microsoft/calculator` is open source, and every key it binds is a
`<data name="<button>.[using:CalculatorApp.Common]KeyboardShortcutManager.<kind>">`
entry in `src/Calculator/Resources/en-US/Resources.resw`. `shortcuts.json` beside
this file is that table, extracted verbatim; `--refresh` re-derives it. So this
overlay does not depend on a blog post agreeing with the app, which is the usual
failure mode for Calculator lists (measured: the widely-cited ones disagree with
each other about the mode keys and omit half the trigonometry).

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/calc/fetch_icons.py [--refresh]

⚠️ THIS IS THE *SCIENTIFIC* MODE OVERLAY, and it has to be one mode or the other.
Three F-keys mean different things per mode in Calculator's own table --
F3 is GRAD *and* DWORD, F4 is DEG *and* WORD, F5 is RAD *and* HEX -- so a keycap
cannot show both. Scientific wins because that is where the ~50 letter shortcuts
live, and the letters are what nobody memorises. The programmer-only keys (QWORD,
DEC/OCT/BIN/BYTE, the bitwise AND/OR/XOR/NOT/Lsh/Rsh) are deliberately left off
rather than mixed in.

⚠️ A HANDFUL OF ENTRIES ASSUME A US LAYOUT. Calculator binds some buttons to a
CHARACTER rather than a key -- `@` is square root, `#` is x^3, `!` is factorial --
and a character lands on whichever key produces it. Those are placed on the US
positions (Shift+2, Shift+3, Shift+1); on a German layout the same characters are
elsewhere and those three keycaps will be wrong. The ~50 letter and F-key entries
are keyed by VIRTUAL KEY and are layout-independent.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RESW_URL = ("https://raw.githubusercontent.com/microsoft/calculator/main/"
            "src/Calculator/Resources/en-US/Resources.resw")
SHORTCUT_KIND = ".[using:CalculatorApp.Common]KeyboardShortcutManager."

# The UI actions, where a real icon beats the word. Everything else on this
# overlay is a mathematical function, and a function's NAME is its symbol -- no
# icon set has ever drawn "arc hyperbolic cosine" and none ever will.
FLUENT = {
    "history":   "History",
    "clearhist": "Delete",
    "copy":      "Copy",
    "paste":     "Clipboard Paste",
    "backspace": "Backspace",
    "graph":     "Data Line",
    # ⚠️ The ESC program mark is BAKED here, unlike the nine overlays that take
    # the curated generic from `app_icons.yaml`. It has to be: on Windows 11 the
    # packaged apps run inside `ApplicationFrameHost.exe`, so the app NAME the
    # window tracker reports is the host, and a slug keyed on "calculator" could
    # never resolve. `app_icons.yaml` says so in its own note. The overlay gets
    # here by window TITLE instead, and a baked mark rides along with it.
    "progmark":  "Calculator",
}

# label -> filename. Drawn as text, white on transparent, so the binding renders
# them with `mode: alpha`.
#
# ⚠️ SIZED BY LENGTH, not fitted per label. Auto-fitting each one would draw
# `sin` and `cos` at different sizes because one is a pixel wider -- the trap the
# Paint.NET line-width composites hit. A ladder keeps every member of a family
# identical (all six `xxxh` hyperbolics agree, all six `axxxh` inverses agree)
# while still filling the keycap, which a single static size cannot do across
# labels from one character to five.
#
# ⚠️ The ladder is a STARTING size and `_fit` shrinks from it, because length
# is a proxy for width and an imperfect one: `GRAD` is four all-caps characters
# and 41 px wide where `sinh` is four lowercase and 31. Without the shrink it was
# drawn CLIPPED -- the rendered sheet read "GRAL" -- which no amount of reading
# the table would have caught, and which a per-label fit would have avoided at
# the cost of the family consistency above. Shrinking keeps both: a label only
# leaves its class when it physically cannot stay in it.
TEXT_SIZE_BY_LENGTH = {1: 28, 2: 26, 3: 20, 4: 17, 5: 14}

# ⚠️ One SEMANTIC family the length rule splits, so it is named explicitly.
# DEG / RAD / GRAD sit on F4 / F5 / F3, adjacent and read as a set of three -- but
# `GRAD` is four characters and shrinks to 13 while `DEG` and `RAD` stay at 20,
# and the odd one out reads as a mistake rather than as a longer word. Pinning
# all three to what the longest can hold is the only way the row looks like one
# control. Seen on the rendered sheet; invisible from the table.
TEXT_SIZE_OVERRIDE = {"grad": 13, "deg": 13, "rad": 13, "degctrl": 13}
TEXT_FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
TEXT_CELL = (40, 36)
TEXT_SS = 8                     # supersample; the save downscales to 4x the cell

TEXT = {
    # --- scientific functions, no modifier -------------------------------
    "sin": "sin", "cos": "cos", "tan": "tan",
    "sec": "sec", "csc": "csc", "cot": "cot",
    "ln": "ln", "log": "log",
    "recip": "1/x", "pi": "π", "sqr": "x²", "powy": "xʸ",
    "twopow": "2ˣ", "exp": "Exp", "ftoe": "F-E", "dms": "dms",
    # ⚠️ `3√x` rather than U+221B CUBE ROOT: Liberation Sans has no such
    # glyph, and a missing glyph is NOT blank -- it draws `.notdef`, a hollow box,
    # which is exactly what the first rendered sheet showed. `_check_glyphs`
    # refuses such a label now instead of shipping one.
    "cbrt": "3√x", "grad": "GRAD", "deg": "DEG", "rad": "RAD",
    "negate": "+/-", "clearentry": "CE", "equals": "=",
    "sqrt": "√", "cube": "x³", "fact": "n!",
    # --- inverse functions, Shift ----------------------------------------
    "asin": "asin", "acos": "acos", "atan": "atan",
    "asec": "asec", "acsc": "acsc", "acot": "acot",
    "logy": "logy", "euler": "e", "rand": "rand",
    # --- hyperbolic + memory, Ctrl ---------------------------------------
    "sinh": "sinh", "cosh": "cosh", "tanh": "tanh",
    "sech": "sech", "csch": "csch", "coth": "coth",
    "epow": "eˣ", "tenpow": "10ˣ", "ysqrt": "ʸ√x",
    "degctrl": "DEG",
    "ms": "MS", "mplus": "M+", "mminus": "M-", "mr": "MR", "mc": "MC",
    # --- inverse hyperbolic, Ctrl+Shift ----------------------------------
    "asinh": "asinh", "acosh": "acosh", "atanh": "atanh",
    "asech": "asech", "acsch": "acsch", "acoth": "acoth",
}


def refresh_shortcuts(out: Path) -> int:
    """Re-derive shortcuts.json from Calculator's own resource file."""
    with urllib.request.urlopen(RESW_URL, timeout=30) as response:
        root = ET.fromstring(response.read())
    table: dict[str, dict[str, str]] = {}
    for data in root.findall("data"):
        name = data.get("name", "")
        if SHORTCUT_KIND not in name:
            continue
        button, kind = name.split(SHORTCUT_KIND)
        table.setdefault(button, {})[kind] = (data.findtext("value") or "").strip()
    out.write_text(json.dumps(table, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"  shortcuts.json  <- {len(table)} buttons from {RESW_URL}")
    return len(table)


def _check_glyphs() -> None:
    """Refuse a label the font cannot draw, BEFORE anything is written.

    ⚠️ A missing glyph is not blank -- FreeType draws `.notdef`, a hollow
    rectangle, which has a perfectly good bounding box and sails through every
    size and clipping check below. U+221B CUBE ROOT is absent from Liberation
    Sans and shipped as a box in the first render; U+207B SUPERSCRIPT MINUS is
    absent too, which is why the inverse functions are spelled `asin` rather than
    `sin⁻¹`. Reading the table cannot catch this and neither can rendering
    unless somebody looks; asking the cmap can.
    """
    from fontTools.ttLib import TTFont
    with TTFont(TEXT_FONT, lazy=True) as font:
        have = set(font.getBestCmap())
    missing = {label: [c for c in label if ord(c) not in have]
               for label in TEXT.values()}
    missing = {k: v for k, v in missing.items() if v}
    if missing:
        raise SystemExit(
            f"{TEXT_FONT} cannot draw: " +
            "; ".join(f"{k!r} is missing " + " ".join(f"U+{ord(c):04X}" for c in v)
                      for k, v in missing.items()))


def _fit(draw, label: str, name: str = "") -> ImageFont.FreeTypeFont:
    """The size for this label, shrunk until its ink fits the cell."""
    size = TEXT_SIZE_OVERRIDE.get(
        name, TEXT_SIZE_BY_LENGTH.get(len(label),
                                      min(TEXT_SIZE_BY_LENGTH.values())))
    while size > 6:
        font = ImageFont.truetype(TEXT_FONT, size * TEXT_SS)
        box = draw.textbbox((0, 0), label, font=font)
        if (box[2] - box[0] <= TEXT_CELL[0] * TEXT_SS
                and box[3] - box[1] <= TEXT_CELL[1] * TEXT_SS):
            return font
        size -= 1
    raise SystemExit(f"{label!r} does not fit {TEXT_CELL} at any size")


def _draw_text(path: Path, label: str, name: str = "") -> None:
    """One label, centred on its INK rather than on its font metrics.

    ⚠️ Centring on the text origin instead would put every label a couple of
    pixels high and leave the descender-less ones visibly off -- the labels here
    are a mix of all-caps (`GRAD`), x-height (`sin`) and superscripts (`x²`),
    so the font's own vertical metrics describe none of them.
    """
    cw, ch = TEXT_CELL
    width, height = cw * TEXT_SS, ch * TEXT_SS
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _fit(draw, label, name)
    box = draw.textbbox((0, 0), label, font=font)
    draw.text(((width - (box[2] - box[0])) / 2 - box[0],
               (height - (box[3] - box[1])) / 2 - box[1]),
              label, font=font, fill=(255, 255, 255, 255))
    image.resize((cw * 4, ch * 4), Image.LANCZOS).save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true",
                        help="re-derive shortcuts.json from the Calculator repo")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    out = here / "icons"
    out.mkdir(exist_ok=True)
    if args.refresh:
        refresh_shortcuts(here / "shortcuts.json")

    _check_glyphs()
    count = icon_fetch.fluent(FLUENT, out)
    for name, label in TEXT.items():
        path = out / f"{name}.png"
        # ⚠️ Guarded so a re-run never clobbers a hand-tuned glyph.
        if path.exists():
            print(f"  {name}.png  <- committed asset (left as-is)")
        else:
            _draw_text(path, label, name)
            print(f"  {name}.png  <- drawn: {label!r}")
        count += 1

    print(f"Wrote {count} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
