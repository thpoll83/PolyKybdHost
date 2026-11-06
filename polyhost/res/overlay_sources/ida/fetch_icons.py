#!/usr/bin/env python3
"""Fetch + render the IDA Pro shortcut icons (reproducible).

The IDA, Binary Ninja and Ghidra sets use the same icons for the same actions
(go to address, cross references, rename, comment, decompile, ...), so the
three tools look alike on the keycaps:

* `BORROWED` copies an icon byte for byte from `../ghidra/icons`.
* `FLUENT` renders Microsoft Fluent UI System Icons (MIT), or Material Symbols
  (Apache-2.0) where the spec is `ms:<name>`.
* `COMPOSITES` draws a glyph over a short word, 1-bit at 40x40, with the
  drawing code of `../ghidra/fetch_icons.py` (the same font, sizes and arrow),
  so a composite here matches the Ghidra composites pixel for pixel in style.

The ESC mark is traced from the public-domain portrait the IDA logo is cropped
from (Madame de Maintenon, 17th century, Wikimedia Commons
`File:Mme_de_Maintenon.jpg`). Hex-Rays does not publish the application icon
as a file. See SOURCES.md.

    pip install cairosvg
    python polyhost/res/overlay_sources/ida/fetch_icons.py
    # with a downloaded copy of the portrait:
    POLYKYBD_IDA_PORTRAIT=Mme_de_Maintenon.jpg python .../ida/fetch_icons.py
"""
from __future__ import annotations

import importlib.util
import io
import os
import sys
import urllib.request
from pathlib import Path

import numpy as np
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


# Same action as in the Ghidra set: the same icon file.
BORROWED = {f"{n}.png": "ghidra" for n in (
    "disassemble", "clear", "label", "comment", "function", "goto", "references",
    "array", "structure", "markselect", "autoanalyze", "decompiler", "casts",
    "bookmarks", "addbookmark", "searchtext", "registers", "functiongraph",
    "symboltable", "nextcomponent", "prevcomponent", "lastactive", "scripts",
    "import", "export", "editfield", "forward",
    "cycle_int", "type_retype", "next_ins", "next_data", "next_undef", "next_bytes",
    "next_func", "prev_func", "next_highlight", "prev_highlight",
    "next_window", "prev_window",
    # glyphs used only inside the composites below
    "g_list", "g_search", "g_pointer", "g_edit", "g_cycle",
)}

FLUENT = {
    "jump_newwin": "Window New",
    "calculator": "Calculator",
    "cli": "ms:terminal",
    "flags": "Flag",
    "fitwindow": "Arrow Fit",
    "center": "Center Vertical",
    "breakpoint": "Record",
    "run": "Play",
    "terminate": "Stop",
    "stepinto": "ms:step_into",
    "stepover": "ms:step_over",
    "stepout": "ms:step_out",
    "debugger": "Bug",
    "plugins": "Puzzle Piece",
    "snapshot": "Camera",
    # glyphs used only inside the composites below
    "g_quote": "Text Quote",
    "g_align": "Align Left",
    "g_bookmark": "Bookmark",
    "g_window": "Window",
    "g_cloud": "ms:cloud_download",
    "g_cloud_up": "ms:cloud_upload",
}

# name -> (glyph, word); a glyph is an icon stem from above, an arrow
# ("up", "down", "left", "right") or "text:<chars>" (drawn large).
COMPOSITES = {
    # create / undefine
    "make_str": ("g_quote", "STR"),
    "func_end": ("function", "END"),
    "func_edit": ("function", "EDIT"),
    "rename_reg": ("editfield", "REG"),
    "align": ("g_align", "ALGN"),
    # operand representation
    "op_hex": ("text:0x", "HEX"),
    "op_dec": ("text:10", "DEC"),
    "op_bin": ("text:01", "BIN"),
    "op_char": ("text:'a'", "CHAR"),
    "op_num": ("text:#", "NUM"),
    "op_offset": ("g_pointer", "OFS"),
    "op_offset_cs": ("g_pointer", "CS"),
    "op_offset_any": ("g_pointer", "ANY"),
    "op_offset_user": ("g_pointer", "USER"),
    "op_structofs": ("structure", "OFS"),
    "op_stackvar": ("text:SP", "VAR"),
    "op_enum": ("g_list", "ENUM"),
    "op_segment": ("text:ds:", "SEG"),
    "op_sign": ("text:±", "SIGN"),
    "op_not": ("text:~", "NOT"),
    "op_zeroes": ("text:00", "ZERO"),
    # comments and lines
    "comment_rpt": ("comment", "RPT"),
    "comment_pseudo": ("comment", "C"),
    "lines_before": ("comment", "PRE"),
    "lines_after": ("comment", "POST"),
    # decompiler
    "pseudo_toggle": ("lastactive", "C"),
    "map_var": ("text:=", "MAP"),
    "paren_pair": ("text:( )", "PAIR"),
    "c_file": ("export", "C"),
    # jumps
    "jump_name": ("goto", "NAME"),
    "jump_func": ("goto", "FUNC"),
    "jump_seg": ("goto", "SEG"),
    "jump_sreg": ("goto", "SREG"),
    "jump_problem": ("goto", "PROB"),
    "jump_entry": ("goto", "ENTR"),
    "jump_bookmark": ("g_bookmark", "JUMP"),
    "xrefs_to": ("references", "TO"),
    "xrefs_from": ("references", "FROM"),
    # search
    "search_bytes": ("g_search", "BYTE"),
    "search_imm": ("g_search", "IMM"),
    "next_text": ("down", "TEXT"),
    "next_imm": ("down", "IMM"),
    "next_explored": ("down", "EXPL"),
    "next_susp": ("down", "SUSP"),
    "next_error": ("down", "ERR"),
    "reg_def": ("up", "DEF"),
    "reg_use": ("down", "USE"),
    "reg_value": ("text:R=", "VAL"),
    # structures, segments, stack
    "struct_var": ("structure", "VAR"),
    "union_member": ("structure", "UNIO"),
    "strlit_style": ("g_quote", "STYL"),
    "data_setup": ("g_cycle", "SET"),
    "stack_ptr": ("text:SP", "EDIT"),
    "stack_vars": ("symboltable", "STCK"),
    "seg_edit": ("text:ds:", "EDIT"),
    "sreg_value": ("text:ds:", "SREG"),
    # subviews (Shift+F-keys): a table over the name of the list
    "view_types": ("symboltable", "TYPE"),
    "view_funcs": ("symboltable", "FUNC"),
    "view_names": ("symboltable", "NAME"),
    "view_sigs": ("symboltable", "SIG"),
    "view_segs": ("symboltable", "SEG"),
    "view_sregs": ("symboltable", "SREG"),
    "view_tils": ("symboltable", "TIL"),
    "view_strings": ("symboltable", "STR"),
    "quick_view": ("g_window", "VIEW"),
    "quick_dbg": ("g_window", "DBG"),
    "output": ("g_window", "OUT"),
    # scripts and files
    "idc_line": ("scripts", "LINE"),
    "recent_scripts": ("scripts", "LAST"),
    "asm_file": ("export", "ASM"),
    "load_header": ("import", "HDR"),
    "manual_operand": ("g_edit", "OPND"),
    "manual_ins": ("g_edit", "INS"),
    "snapshot_mgr": ("snapshot", "LIST"),
    "fullscreen": ("fitwindow", "FULL"),
    "zoom100": ("text:1:1", "ZOOM"),
    # debugger
    "run_to_cursor": ("run", "HERE"),
    "set_ip": ("right", "IP"),
    "bp_list": ("breakpoint", "LIST"),
    "bp_find": ("breakpoint", "FIND"),
    "stack_trace": ("g_list", "TRCE"),
    # Lumina
    "lumina_pull": ("g_cloud", "PULL"),
    "lumina_push": ("g_cloud_up", "PUSH"),
    "lumina_view": ("g_cloud", "VIEW"),
    "highlight_lock": ("text:H", "LOCK"),
}
# Alt+1..9 (Control+1..9 on macOS): switch to window N.
COMPOSITES.update({f"window_{n}": (f"text:{n}", "WIN") for n in range(1, 10)})
# Ctrl+Alt+1..8: lock the highlight in colour slot N.
COMPOSITES.update({f"highlight_{n}": (f"text:H{n}", "LOCK") for n in range(1, 9)})

# The ESC mark: a 32x32 1-bit trace, placed 1:1 by program_icon_region [37, 32].
PORTRAIT_URL = "https://upload.wikimedia.org/wikipedia/commons/a/a4/Mme_de_Maintenon.jpg"
PORTRAIT_CROP = (100, 50, 225, 175)   # the head, in the 280x346 file
PORTRAIT_DARK = 100                   # luma below this is lit (hair, eyes, mouth)
MARK = 32


def composites(out: Path) -> None:
    """Draw COMPOSITES with the Ghidra set's drawing code (guarded per file)."""
    g = ghidra_helpers()
    g.COMPOSITES = COMPOSITES
    g.ISA = {}
    g.composites(out)


def portrait_mark(dest: Path) -> None:
    """The head of the portrait, dark pixels lit, the sky behind it removed."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    local = os.environ.get("POLYKYBD_IDA_PORTRAIT")   # a downloaded copy
    if local:
        data = Path(local).read_bytes()
    else:   # Wikimedia answers 429 to repeated requests; then use the variable
        data = urllib.request.urlopen(urllib.request.Request(
            PORTRAIT_URL, headers={"User-Agent": "polykybd (noreply@anthropic.com)"}),
            timeout=30).read()
    img = Image.open(io.BytesIO(data)).convert("RGB").crop(PORTRAIT_CROP)
    a = np.asarray(img).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    sky = (b >= r - 8) & (luma > 80)          # the blue-grey background
    lit = (luma < PORTRAIT_DARK) & ~sky
    mask = Image.fromarray((lit * 255).astype("uint8")).resize((MARK, MARK), Image.LANCZOS)
    mask = mask.point(lambda v: 255 if v >= 128 else 0)
    out = Image.new("RGBA", (MARK, MARK), (255, 255, 255, 0))
    out.putalpha(mask)
    out.save(dest)
    print(f"  {dest.name}  <- traced from Mme_de_Maintenon.jpg")


def main() -> int:
    out = HERE / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.borrow(BORROWED, out)
    icon_fetch.fluent(FLUENT, out)
    composites(out)
    portrait_mark(out / "ida.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
