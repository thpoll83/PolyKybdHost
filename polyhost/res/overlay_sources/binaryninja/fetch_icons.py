#!/usr/bin/env python3
"""Fetch + render the Binary Ninja shortcut icons (reproducible).

The Binary Ninja, IDA and Ghidra sets use the same icons for the same actions,
so the three tools look alike on the keycaps:

* `BORROWED` copies an icon byte for byte from `../ghidra/icons` or
  `../ida/icons`.
* `FLUENT` renders Microsoft Fluent UI System Icons (MIT), or Material Symbols
  (Apache-2.0) where the spec is `ms:<name>`.
* `COMPOSITES` draws a glyph over a short word, 1-bit at 40x40, with the
  drawing code of `../ghidra/fetch_icons.py`.

The ESC mark is traced from the Binary Ninja logo in the binaryninja-api
repository (`docs/img/logo.png`). See SOURCES.md.

    pip install cairosvg
    python polyhost/res/overlay_sources/binaryninja/fetch_icons.py
"""
from __future__ import annotations

import importlib.util
import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

HERE = Path(__file__).resolve().parent


def ghidra_helpers():
    """`../ghidra/fetch_icons.py` as a module, for its composite drawing code."""
    spec = importlib.util.spec_from_file_location(
        "ghidra_fetch_icons", HERE.parent / "ghidra" / "fetch_icons.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Same action as in the Ghidra or IDA set: the same icon file.
BORROWED = {f"{n}.png": "ghidra" for n in (
    "disassemble", "clear", "label", "comment", "function", "goto", "references",
    "array", "structure", "functiongraph", "actionchooser", "keybinding",
    "back", "forward", "cycle_int", "type_retype", "pointer", "patch_ins",
    "symboltable", "lastactive",
    # glyphs used only inside the composites below
    "g_cycle",
)}
BORROWED.update({f"{n}.png": "ida" for n in (
    "make_str", "op_char", "op_sign", "op_not", "op_enum", "pseudo_toggle",
    "view_types", "plugins", "breakpoint", "run", "run_to_cursor",
    "stepinto", "stepover", "stepout",
    # glyphs used only inside the composites below
    "g_quote",
)})

FLUENT = {
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "openurl": "Globe",
    "settings": "Settings",
    "pause": "Pause",
    "rewind": "ms:fast_rewind",
    # glyphs used only inside the composites below
    "g_open": "Folder Open",
}

# name -> (glyph, word); see ../ghidra/fetch_icons.py for the glyph forms.
COMPOSITES = {
    "hexview": ("text:FF", "VIEW"),
    "il_cycle": ("g_cycle", "IL"),
    "propagate": ("right", "PROP"),
    "make_wstr": ("g_quote", "WSTR"),
    "make_w32": ("g_quote", "W32"),
    "int8": ("text:i8", "INT"),
    "int16": ("text:i16", "INT"),
    "int32": ("text:i32", "INT"),
    "int64": ("text:i64", "INT"),
    "float_cycle": ("g_cycle", "FLT"),
    "toggle_hexdec": ("text:0x", "DEC"),
    "merge_here": ("text:+", "MRG"),
    "merge_dialog": ("text:=", "VARS"),
    "xref_next": ("down", "XREF"),
    "xref_prev": ("up", "XREF"),
    "open_options": ("g_open", "OPT"),
    "palette_all": ("actionchooser", "ALL"),
    "settings_file": ("settings", "FILE"),
    "hw_breakpoint": ("breakpoint", "HW"),
    "resume": ("run", "CONT"),
    "stepinto_back": ("stepinto", "BACK"),
    "stepover_back": ("stepover", "BACK"),
    "stepout_back": ("stepout", "BACK"),
    "run_back_here": ("rewind", "HERE"),
    "ttd_time": ("goto", "TIME"),
}
# Ctrl+1..0 go to bookmark N; Ctrl+Alt+1..0 set bookmark N (0 is bookmark 10).
for _n in range(1, 11):
    COMPOSITES[f"bookmark_go_{_n}"] = (f"text:{_n}", "BKMK")
    COMPOSITES[f"bookmark_set_{_n}"] = (f"text:+{_n}", "BKMK")

LOGO_URL = ("https://raw.githubusercontent.com/Vector35/binaryninja-api/"
            "ee77e014bd3f9ced378ae673afdbb34ae04a93c1/docs/img/logo.png")
MARK = 32           # placed 1:1 by program_icon_region [37, 32]
MARK_DARK = 60      # luma below this is lit: the black ring and the mask outline


def logo_mark(dest: Path) -> None:
    """The logo over white, contain-fit to 32x32 (LANCZOS), dark pixels lit."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    data = urllib.request.urlopen(
        urllib.request.Request(LOGO_URL, headers={"User-Agent": "polykybd"}),
        timeout=30).read()
    logo = Image.open(io.BytesIO(data)).convert("RGBA")
    flat = Image.new("RGBA", logo.size, (255, 255, 255, 255))
    flat.alpha_composite(logo)
    luma = flat.convert("L").resize((MARK, MARK), Image.LANCZOS)
    mask = luma.point(lambda v: 255 if v < MARK_DARK else 0)
    out = Image.new("RGBA", (MARK, MARK), (255, 255, 255, 0))
    out.putalpha(mask)
    out.save(dest)
    print(f"  {dest.name}  <- traced from binaryninja-api docs/img/logo.png")


def main() -> int:
    out = HERE / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.borrow(BORROWED, out)
    icon_fetch.fluent(FLUENT, out)
    g = ghidra_helpers()
    g.COMPOSITES = COMPOSITES
    g.ISA = {}
    g.composites(out)
    logo_mark(out / "binaryninja.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
