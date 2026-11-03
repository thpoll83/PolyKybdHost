#!/usr/bin/env python3
"""Fetch + render the Arduino IDE 2.x shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). Where the action is the
same as in the VS Code, Sublime, JetBrains or Zed sets, the same glyph name is
used, so the editor keys look alike across the IDEs.

Also used:
* `../editor_glyphs.py` for the multiple-cursor keys (drawn, shared with
  Sublime and Zed).
* `deleteline.png` copied from `../jetbrains/icons/` (shared drawing).
* `arrow_icon()` below: a Fluent glyph with an up or down arrow beside it,
  drawn 1-bit at 40x40, for copy line up/down, next/previous problem and find previous.
* The ESC mark is the Arduino logo from Simple Icons (CC0 artwork; nominative
  use, see `../brand_marks.py`).

    pip install cairosvg
    python polyhost/res/overlay_sources/arduino_ide/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import (  # noqa: E402
    brand_marks, editor_glyphs, icon_fetch)

FLUENT = {
    # --- sketch / file (Arduino's own commands) ---
    "newsketch": "Document Add",
    "newcloud": "Cloud Add",
    "saveas": "Save Edit",
    "closesketch": "Dismiss",
    "verify": "Checkmark",
    "verifyclean": "Broom",
    "exportbin": "Arrow Export LTR",
    "upload": "Arrow Upload",
    "uploadprog": "Developer Board Lightning",
    "sketchfolder": "Folder",
    "newtab": "Tab Add",
    "prevtab": "Arrow Previous",
    "nexttab": "Arrow Next",
    "forum": "ms:forum",
    "gotoline": "Number Symbol",
    "comment": "Comment",
    "usesel": "ms:feature_search",
    "autoformat": "ms:auto_fix_high",
    "fontup": "Font Increase",
    "fontdown": "Font Decrease",
    "reference": "Book Search",
    "library": "Library",
    "sketchbook": "Notebook",
    "serialmonitor": "Serial Port",
    "problems": "Warning",
    # --- editor (Theia / Monaco keys Arduino keeps) ---
    "commandpalette": "Apps List Detail",
    "suggest": "Text Grammar Wand",
    "paraminfo": "Braces Variable",
    "quickfix": "Lightbulb",
    "definition": "Target",
    "references": "ms:manage_search",
    "peekdefinition": "Eye",
    "peekimpl": "Glasses",
    "rename": "Rename",
    "gotosymbol": "Text Bullet List Tree",
    "selectall": "Select All On",
    "movelineup": "ms:move_up",
    "movelinedown": "ms:move_down",
    "lineabove": "ms:add_row_above",
    "linebelow": "ms:add_row_below",
    "indent": "Text Indent Increase",
    "outdent": "Text Indent Decrease",
    "matchbracket": "Braces",
    "fold": "Text Collapse",
    "unfold": "Text Expand",
    "wordwrap": "Text Wrap",
    "bottompanel": "Panel Bottom",
    "fullscreen": "Full Screen Maximize",
    "blockcomment": "Comment Multiple",
    "expandsel": "Arrow Expand",
    "shrinksel": "Arrow Minimize",
    "lineends": "Text Align Right",
    "contextmenu": "More Vertical",
    "keyboardshortcuts": "Keyboard",
    "devtools": "Window Dev Tools",
    "lastedit": "Edit Arrow Back",
    "reopentab": "Tab Desktop Arrow Clockwise",
    "navback": "Arrow Left",
    "navforward": "Arrow Right",
    "closeothers": "Dismiss Square Multiple",
    "closetab": "Tab Prohibited",
    "matchcase": "ms:match_case",
    "wholeword": "Text Whole Word",
    "regex": "ms:regular_expression",
    "findinselection": "Select Object",
    # --- debugger (Theia keys; act once a debug session runs) ---
    "debugview": "Bug",
    "stopdebug": "Stop",
    "restart": "Arrow Clockwise",
    "pause": "Pause",
    "breakpoint": "Record",
    "stepover": "Arrow Step Over",
    "stepout": "Arrow Step Out",
}

DRAWN = ["multicursor", "cursorabove", "cursorbelow"]
BORROWED = {"deleteline.png": "jetbrains"}

# Glyph + arrow composites: {file: (Fluent spec, arrow points up)}.
ARROWED = {
    "copylineup": ("Copy", True),
    "copylinedown": ("Copy", False),
    "nextproblem": ("Warning", False),
    "prevproblem": ("Warning", True),
    "findprev": ("Search Square", True),
}
SIZE = 40      # drawn at keycap size, bound with region [40, 40]
GLYPH = 30     # the Fluent glyph, left
ARROW_X = 34   # centre of the arrow, right


def _glyph_mask(spec: str, px: int) -> Image.Image:
    svg, _asset, _src = icon_fetch._fetch_svg(spec)
    png = cairosvg.svg2png(bytestring=svg, output_width=px, output_height=px)
    alpha = Image.open(io.BytesIO(png)).convert("RGBA").split()[3]
    return alpha.point(lambda v: 255 if v >= 110 else 0)


def arrow_icon(dest: Path, spec: str, up: bool) -> None:
    """A Fluent glyph on the left with a 1-bit arrow on the right, 40x40."""
    mask = Image.new("L", (SIZE, SIZE), 0)
    mask.paste(_glyph_mask(spec, GLYPH), (0, (SIZE - GLYPH) // 2))
    d = ImageDraw.Draw(mask)
    top, bot, head = 6, SIZE - 6, 7
    d.rectangle([ARROW_X - 1, top + 4, ARROW_X + 1, bot - 4], fill=255)
    if up:
        d.polygon([(ARROW_X, top), (ARROW_X - 5, top + head), (ARROW_X + 5, top + head)], fill=255)
    else:
        d.polygon([(ARROW_X, bot), (ARROW_X - 5, bot - head), (ARROW_X + 5, bot - head)], fill=255)
    img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    img.putalpha(mask)
    img.save(dest)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += editor_glyphs.draw_all(out, DRAWN)
    n += icon_fetch.borrow(BORROWED, out)
    for name, (spec, up) in ARROWED.items():
        dest = out / f"{name}.png"
        if dest.exists():
            print(f"  {dest.name}  <- committed asset (left as-is)")
            continue
        arrow_icon(dest, spec, up)
        print(f"  {dest.name}  <- drawn: {spec} + {'up' if up else 'down'} arrow")
        n += 1
    brand_marks.ensure(out / "arduino.png", "arduino")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
