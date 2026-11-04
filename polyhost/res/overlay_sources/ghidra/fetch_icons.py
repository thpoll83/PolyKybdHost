#!/usr/bin/env python3
"""Fetch + render the Ghidra CodeBrowser shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries).

Several families of actions differ only by a word ("Next instruction / data /
undefined / label", "Cycle int / string", "Patch instruction / data"). Each of
those is a composite drawn 1-bit at 40x40 by `composites()`: a glyph or an arrow
in the top 24 rows and a short word below it in Liberation Sans Bold. The
generator scales the whole image into its region, so a 40x40 image bound with
`region: [40, 40]` is placed 1:1.

The ESC mark is the Ghidra logo from the Ghidra repository (Apache-2.0,
`GhidraDocs/images/GHIDRA_1.png`, listed as GHIDRA licence in
`GhidraDocs/certification.manifest`): the infinity-shaped dragon, without the
word mark under it.

    pip install cairosvg
    python polyhost/res/overlay_sources/ghidra/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

FLUENT = {
    # single keys (Listing)
    "disassemble": "Code",
    "clear": "Eraser",
    "label": "Tag",
    "labelhistory": "History",
    "comment": "Comment",
    "function": "ms:function",
    "equate": "ms:equal",
    "references": "Link",
    "markselect": "Select Object",
    "goto": "ms:jump_to_element",
    "import": "Arrow Import",
    "export": "Arrow Export",
    "autoanalyze": "Wand",
    "programdiff": "ms:difference",
    "expand": "ms:unfold_more",
    "array": "ms:data_array",
    "structure": "Braces",
    "keybinding": "Keyboard",
    "refresh": "Arrow Clockwise",
    "contextmenu": "ms:menu_open",
    # Ctrl (Cmd) keys
    "decompiler": "Document Code",
    "bookmarks": "Bookmark Multiple",
    "addbookmark": "Bookmark Add",
    "symboltable": "Table",
    "registers": "ms:memory",
    "searchtext": "ms:manage_search",
    "highlight": "Highlight",
    "datagraph": "ms:hub",
    "filesystem": "Folder Zip",
    "actionchooser": "ms:bolt",
    "functiongraph": "Flowchart",
    "fontup": "Font Increase",
    "fontdown": "Font Decrease",
    "nextcomponent": "Arrow Next",
    "prevcomponent": "Arrow Previous",
    "lastactive": "Arrow Swap",
    "gotoprogram": "Document Bullet List",
    "togglesearchdir": "Arrow Sort",
    "defaultref": "ms:add_link",
    "editfield": "Rename",
    "scripts": "Script",
    "cloneview": "Window Multiple",
    # glyphs used only inside the composites below
    "back": "Arrow Left",
    "forward": "Arrow Right",
    "g_cycle": "Arrow Sync",
    "g_list": "Text Bullet List",
    "g_repeat": "Arrow Repeat All",
    "g_edit": "Edit",
    "g_pointer": "ms:arrow_right_alt",
    "g_search": "Search",
    "g_wrench": "Wrench",
    "g_replay": "ms:replay",
}

# name -> (glyph, word). A glyph is a FLUENT stem above, an arrow
# ("up", "down", "left", "right"), "void" (an empty-set sign), or
# "text:<chars>" (the characters drawn large in the glyph area).
COMPOSITES = {
    "cycle_int": ("g_cycle", "INT"),
    "cycle_str": ("g_cycle", "STR"),
    "type_choose": ("g_list", "TYPE"),
    "type_repeat": ("g_repeat", "TYPE"),
    "type_retype": ("g_edit", "TYPE"),
    "type_edit": ("structure", "EDIT"),
    "pointer": ("g_pointer", "PTR"),
    "void": ("void", "VOID"),
    "casts": ("text:(T)", "CAST"),
    "memsearch": ("g_search", "MEM"),
    "finduses": ("g_search", "USES"),
    "search_next": ("g_search", "NEXT"),
    "search_prev": ("g_search", "PREV"),
    "patch_ins": ("g_wrench", "INS"),
    "patch_data": ("g_wrench", "DATA"),
    "rerun_script": ("g_replay", "SCPT"),
    "refs_back": ("references", "BACK"),
    "refs_fwd": ("references", "FWD"),
    "next_ins": ("down", "INS"),
    "next_data": ("down", "DATA"),
    "next_undef": ("down", "UNDF"),
    "next_label": ("down", "LBL"),
    "next_func": ("down", "FUN"),
    "prev_func": ("up", "FUN"),
    "hist_func_back": ("left", "FUN"),
    "hist_func_fwd": ("right", "FUN"),
    "next_bytes": ("down", "BYTE"),
    "next_bookmark": ("down", "BKMK"),
    "next_diff": ("down", "DIFF"),
    "prev_diff": ("up", "DIFF"),
    "next_highlight": ("down", "HIGH"),
    "prev_highlight": ("up", "HIGH"),
    "prev_token": ("up", "TOKN"),
    "next_selection": ("down", "SEL"),
    "prev_selection": ("up", "SEL"),
    "next_pane": ("down", "PANE"),
    "prev_pane": ("up", "PANE"),
    "next_window": ("down", "WIN"),
    "prev_window": ("up", "WIN"),
    "next_tab": ("right", "TAB"),
    "prev_tab": ("left", "TAB"),
    "next_brace": ("text:}", "NEXT"),
}

# F11 / F12: the language-specific disassemble actions. Two lines of text.
ISA = {"isa_1": ("ARM", "x64"), "isa_2": ("THMB", "x86")}

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
SIZE = (40, 40)
GLYPH_BOX = (0, 0, 40, 24)      # x0, y0, x1, y1 of the glyph area
WORD_PX = 12
GLYPH_TEXT_PX = 22
WORD_BASELINE = 38

LOGO_URL = ("https://raw.githubusercontent.com/NationalSecurityAgency/ghidra/"
            "Ghidra_12.2_build/GhidraDocs/images/GHIDRA_1.png")
LOGO_CROP_BOTTOM = 780          # rows above the "GHIDRA" word mark
LOGO_WIDTH = 480


def _arrow(d: ImageDraw.ImageDraw, direction: str) -> None:
    """A 3 px arrow centred in the glyph area, pointing `direction`."""
    cx, cy = 20, 11
    if direction in ("up", "down"):
        sign = 1 if direction == "down" else -1
        tip, tail = cy + sign * 10, cy - sign * 10
        d.rectangle([cx - 1, min(tip, tail), cx + 1, max(tip, tail)], fill=255)
        d.polygon([(cx, tip + sign), (cx - 8, tip - sign * 8), (cx + 8, tip - sign * 8)],
                  fill=255)
    else:
        sign = 1 if direction == "right" else -1
        tip, tail = cx + sign * 12, cx - sign * 12
        d.rectangle([min(tip, tail), cy - 1, max(tip, tail), cy + 1], fill=255)
        d.polygon([(tip + sign, cy), (tip - sign * 8, cy - 8), (tip - sign * 8, cy + 8)],
                  fill=255)


def _void(d: ImageDraw.ImageDraw) -> None:
    """An empty-set sign: a circle with a slash."""
    d.ellipse([11, 2, 29, 20], outline=255, width=3)
    d.line([(9, 22), (31, 0)], fill=255, width=3)


def _paste_glyph(mask: Image.Image, src: Path) -> None:
    """Scale a fetched glyph into the glyph area and paste its 1-bit alpha."""
    x0, y0, x1, y1 = GLYPH_BOX
    alpha = Image.open(src).convert("RGBA").split()[3]
    bbox = alpha.getbbox()
    alpha = alpha.crop(bbox) if bbox else alpha
    w, h = alpha.size
    scale = min((x1 - x0) / w, (y1 - y0) / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    alpha = alpha.resize((nw, nh), Image.LANCZOS).point(lambda v: 255 if v >= 128 else 0)
    mask.paste(255, (x0 + (x1 - x0 - nw) // 2, y0 + (y1 - y0 - nh) // 2), alpha)


def _save(mask: Image.Image, dest: Path) -> None:
    mask = mask.point(lambda v: 255 if v >= 128 else 0)
    img = Image.new("RGBA", SIZE, (255, 255, 255, 0))
    img.putalpha(mask)
    img.save(dest)


def composites(out: Path) -> None:
    """Draw the glyph + word composites and the two ISA labels, 1-bit at 40x40."""
    font = glyph_font = None
    for name, (glyph, word) in COMPOSITES.items():
        dest = out / f"{name}.png"
        if dest.exists():
            print(f"  {dest.name}  <- committed asset (left as-is)")
            continue
        font = font or ImageFont.truetype(BOLD, WORD_PX)
        mask = Image.new("L", SIZE, 0)
        d = ImageDraw.Draw(mask)
        if glyph in ("up", "down", "left", "right"):
            _arrow(d, glyph)
        elif glyph == "void":
            _void(d)
        elif glyph.startswith("text:"):
            glyph_font = glyph_font or ImageFont.truetype(BOLD, GLYPH_TEXT_PX)
            text = glyph[len("text:"):]
            d.text((SIZE[0] / 2, GLYPH_BOX[3] // 2), text, font=glyph_font,
                   fill=255, anchor="mm")
        else:
            _paste_glyph(mask, out / f"{glyph}.png")
        w = d.textlength(word, font=font)
        if w > SIZE[0]:
            raise ValueError(f"{name}: word {word!r} is {w:.0f} px wide")
        d.text(((SIZE[0] - w) / 2, WORD_BASELINE), word, font=font, fill=255, anchor="ls")
        _save(mask, dest)
        print(f"  {dest.name}  <- drawn {glyph} + '{word}'")
    isa_font = None
    for name, (top, bottom) in ISA.items():
        dest = out / f"{name}.png"
        if dest.exists():
            print(f"  {dest.name}  <- committed asset (left as-is)")
            continue
        isa_font = isa_font or ImageFont.truetype(BOLD, 14)
        mask = Image.new("L", SIZE, 0)
        d = ImageDraw.Draw(mask)
        for text, baseline in ((top, 17), (bottom, 37)):
            w = d.textlength(text, font=isa_font)
            d.text(((SIZE[0] - w) / 2, baseline), text, font=isa_font, fill=255, anchor="ls")
        _save(mask, dest)
        print(f"  {dest.name}  <- drawn '{top}' / '{bottom}'")


def logo(dest: Path) -> None:
    """The Ghidra infinity dragon, cropped above the word mark."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    data = urllib.request.urlopen(
        urllib.request.Request(LOGO_URL, headers={"User-Agent": "polykybd"}),
        timeout=30).read()
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    img = img.crop((0, 0, img.width, LOGO_CROP_BOTTOM))
    img = img.crop(img.getbbox())
    h = round(img.height * LOGO_WIDTH / img.width)
    img.resize((LOGO_WIDTH, h), Image.LANCZOS).save(dest)
    print(f"  {dest.name}  <- GHIDRA_1.png, cropped above the word mark")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    composites(out)
    logo(out / "ghidra.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
