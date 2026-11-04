#!/usr/bin/env python3
"""Fetch + render the Eclipse IDE shortcut icons (reproducible source step).

Four sources, in this order of preference (SOURCES.md lists every file):

1. **Borrowed** from a sibling editor overlay (`icon_fetch.borrow`),
   byte-identical, where the action is the same as one JetBrains, Sublime Text
   or Zed already draws (step into, format, extract method, move lines...).
   Same action, same picture, and the overlay icon library stores it once.
2. **Microsoft Fluent UI System Icons (MIT)**, the house style, and Google
   **Material Symbols (Apache-2.0)** for the gaps (`ms:` specs).
3. **Badges** (`_badge`): a glyph shrunk to the lower left with a small mark
   top right (a triangle for previous/next, a plus, a cross, a slash). Eclipse
   binds many such pairs, and two keys of one modifier layer must not draw the
   same picture for different actions. Same drawing as Zed's composites.
4. **Word composites** (`_worded`): a small glyph above a 3-4 letter word,
   1-bit at 40x40, for a family whose members differ only by a noun: the
   search family (DECL / REFS / TEXT / OCC), next/previous editor, view and
   perspective (EDIT / VIEW / PERS), the two Maven commands (MVN / POM) and two
   method refactorings (SIG / STAT). Bound with `region: [40, 40]` and
   `mode: alpha`.

The ESC **program mark** is the Eclipse IDE logo from Simple Icons
(`eclipseide`, CC0 artwork; nominative use, see `../brand_marks.py`). It and
every drawn composite are guarded: a committed file is never clobbered.

Run from the repo root with the project venv:

    .venv/bin/python polyhost/res/overlay_sources/eclipse/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

# Same action as another editor overlay -> the same committed drawing.
BORROW = {
    # JetBrains: whole-cell drawings, bound with the same 72x40 centred geometry
    "back.png": "jetbrains", "forward.png": "jetbrains",
    "breakpoint.png": "jetbrains", "debug.png": "jetbrains", "run.png": "jetbrains",
    "stepinto.png": "jetbrains", "stepover.png": "jetbrains", "stepout.png": "jetbrains",
    "smartstepinto.png": "jetbrains", "resume.png": "jetbrains", "stop.png": "jetbrains",
    "gotodeclaration.png": "jetbrains", "gotofile.png": "jetbrains",
    "reformat.png": "jetbrains", "rename.png": "jetbrains",
    # JetBrains: Fluent / Material renders, default geometry
    "intentions.png": "jetbrains", "findaction.png": "jetbrains", "build.png": "jetbrains",
    "deleteline.png": "jetbrains", "win_structure.png": "jetbrains",
    "runtocursor.png": "jetbrains", "typehierarchy.png": "jetbrains",
    "callhierarchy.png": "jetbrains", "quickdoc.png": "jetbrains",
    "completion.png": "jetbrains", "paraminfo.png": "jetbrains",
    "evaluate.png": "jetbrains", "optimizeimports.png": "jetbrains",
    "gotoclass.png": "jetbrains", "win_commit.png": "jetbrains",
    "extendselection.png": "jetbrains", "shrinkselection.png": "jetbrains",
    "inline.png": "jetbrains", "extractmethod.png": "jetbrains",
    "introducevariable.png": "jetbrains", "generate.png": "jetbrains",
    "refactorthis.png": "jetbrains",
    # Sublime Text
    "comment.png": "sublime", "blockcomment.png": "sublime", "gotoline.png": "sublime",
    "swapup.png": "sublime", "swapdown.png": "sublime", "joinlines.png": "sublime",
    "insertafter.png": "sublime", "insertbefore.png": "sublime",
    "matchbracket.png": "sublime", "autocomplete.png": "sublime",
    # Zed (its badge composites and Fluent renders)
    "dupup.png": "zed", "dupdown.png": "zed", "nexttab.png": "zed", "prevtab.png": "zed",
    "findprev.png": "zed", "nodeprev.png": "zed", "nodenext.png": "zed",
    "tabswitcher.png": "zed", "saveall.png": "zed", "contextmenu.png": "zed",
    "linenumbers.png": "zed", "hunk.png": "zed", "focusnext.png": "zed",
    "focusprev.png": "zed", "_search.png": "zed", "_code.png": "zed", "_edit.png": "zed",
}

FLUENT = {
    # --- window and navigation ---
    "activateeditor": "Document Edit",
    "maximize": "ms:open_in_full",
    "switcheditor": "Document Multiple",
    "outlinestructure": "ms:list_alt",
    "quickhierarchy": "ms:lan",
    "properties": "ms:page_info",
    "systemmenu": "Navigation",
    "nextpage": "Document Arrow Right",
    "prevpage": "Document Arrow Left",
    "fullscreen": "Full Screen Maximize",
    "showin": "ms:jump_to_element",
    "newmenu": "Add Square",
    "keyassist": "Keyboard",
    "plugin": "Puzzle Piece",
    "closeall": "ms:cancel_presentation",
    "splith": "Split Horizontal",
    "splitv": "Split Vertical",
    "openclipboard": "ms:content_paste_go",
    "findreplace": "ms:find_replace",
    # --- editing ---
    "indent": "Text Indent Increase",
    "uppercase": "Text Case Uppercase",
    "lowercase": "Text Case Lowercase",
    "wordwrap": "Text Wrap",
    "blockselect": "Select Object",
    "insertmode": "Text Edit Style",
    "textblock": "ms:format_quote",
    "addimport": "Arrow Import",
    "javadoc": "Book Add",
    "breadcrumb": "ms:keyboard_double_arrow_right",
    "markocc": "Highlight",
    "move": "Arrow Move",
    "surround": "ms:code_blocks",
    "forcereturn": "ms:keyboard_return",
    "scrollup": "ms:keyboard_double_arrow_up",
    "scrolldown": "ms:keyboard_double_arrow_down",
    # --- debug ---
    "execute": "Play Circle",
    "stepfilters": "Filter",
    "resumeothers": "ms:fast_forward",
    "inspect": "Eye",
    "allinstances": "ms:category",
    "javadocext": "Book Globe",
    # bases for the composites below (underscore = not bound directly)
    "_docsearch": "Document Search",
    "_tabs": "Tabs",
    "_highlight": "Highlight",
    "_record": "Record",
    "_sync": "Arrow Sync",
    "_document": "Document",
    "_function": "ms:function",
    "_arrownext": "Arrow Next",
    "_arrowprev": "Arrow Previous",
}

# composite -> (base file, badge)
BADGED = {
    "findnext.png": ("_search.png", "down"),
    "resultprev.png": ("_docsearch.png", "up"),
    "resultnext.png": ("_docsearch.png", "down"),
    "editprev.png": ("_edit.png", "left"),
    "editnext.png": ("_edit.png", "right"),
    "subtabprev.png": ("_tabs.png", "left"),
    "subtabnext.png": ("_tabs.png", "right"),
    "elemprev.png": ("_code.png", "left"),
    "elemnext.png": ("_code.png", "right"),
    "blockcommentadd.png": ("blockcomment.png", "plus"),
    "blockcommentdel.png": ("blockcomment.png", "x"),
    "deleteeol.png": ("deleteline.png", "right"),
    "occremove.png": ("_highlight.png", "x"),
    "skipbreakpoints.png": ("_record.png", "slash"),
}

# composite -> (base file, word, badge or None)
WORDED = {
    "searchdecl.png": ("_search.png", "DECL", None),
    "searchrefs.png": ("_search.png", "REFS", None),
    "searchtext.png": ("_search.png", "TEXT", None),
    "searchocc.png": ("_search.png", "OCC", None),
    "incfind.png": ("_search.png", "INC", "down"),
    "incfindrev.png": ("_search.png", "INC", "up"),
    "nexteditor.png": ("_arrownext.png", "EDIT", None),
    "preveditor.png": ("_arrowprev.png", "EDIT", None),
    "nextview.png": ("_arrownext.png", "VIEW", None),
    "prevview.png": ("_arrowprev.png", "VIEW", None),
    "nextpersp.png": ("_arrownext.png", "PERS", None),
    "prevpersp.png": ("_arrowprev.png", "PERS", None),
    "mvnupdate.png": ("_sync.png", "MVN", None),
    "mvnpom.png": ("_document.png", "POM", None),
    "changesig.png": ("_function.png", "SIG", None),
    "makestatic.png": ("_function.png", "STAT", None),
}

INK = (0, 0, 0, 255)


def _triangle(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int], kind: str) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    pts = {"up": [(x0, y1), (x1, y1), (cx, y0)],
           "down": [(x0, y0), (x1, y0), (cx, y1)],
           "right": [(x0, y0), (x0, y1), (x1, cy)],
           "left": [(x1, y0), (x1, y1), (x0, cy)]}[kind]
    d.polygon(pts, fill=INK)


def _badge(base: Path, out: Path, kind: str) -> None:
    """`base` shrunk into the lower-left 72% of a 96px canvas + a badge top right.

    Same geometry as Zed's `_badge`, so a pair drawn here reads as one family
    with the ones borrowed from there. Drawn at 4x and downsampled; opaque
    pixels are what the `alpha` mode lights."""
    s = 4
    u = 96 * s
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    g = Image.open(base).convert("RGBA").resize((int(u * 0.72), int(u * 0.72)), Image.LANCZOS)
    img.alpha_composite(g, (0, u - g.height))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = int(u * 0.70), 0, u - 1, int(u * 0.30)
    w = int(u * 0.045)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    if kind in ("up", "down", "left", "right"):
        _triangle(d, (x0, y0, x1, y1), kind)
    elif kind == "x":
        d.line([(x0, y0), (x1, y1)], fill=INK, width=w)
        d.line([(x0, y1), (x1, y0)], fill=INK, width=w)
    elif kind == "plus":
        d.line([(cx, y0), (cx, y1)], fill=INK, width=w)
        d.line([(x0, cy), (x1, cy)], fill=INK, width=w)
    elif kind == "slash":
        # A stroke across the whole glyph: "off" / "skip".
        d.line([(int(u * 0.06), u - int(u * 0.04)), (int(u * 0.70), int(u * 0.30))],
               fill=INK, width=int(u * 0.07))
    else:
        raise ValueError(kind)
    img.resize((96, 96), Image.LANCZOS).save(out)


WORD_SIZE = (40, 40)
WORD_FONT_PX = 13
GLYPH_PX = 22


def _worded(base: Path, out: Path, word: str, badge: str | None) -> None:
    """A 22 px glyph (thresholded to 1 bit) above `word` in Liberation Sans Bold
    13 px, on a 40x40 white-on-transparent canvas.

    Static font size and a fixed baseline, so every word of a family sits at
    the same place and only the word differs. A badge, when given, is a small
    triangle right of the glyph."""
    w, h = WORD_SIZE
    mask = Image.new("L", WORD_SIZE, 0)
    g = Image.open(base).convert("RGBA").resize((GLYPH_PX, GLYPH_PX), Image.LANCZOS)
    a = g.split()[3].point(lambda v: 255 if v >= 110 else 0)
    gx = (w - GLYPH_PX) // 2 if badge is None else 4
    mask.paste(255, (gx, 0), a)
    d = ImageDraw.Draw(mask)
    if badge is not None:
        x0 = gx + GLYPH_PX + 2
        box = (x0, 3, x0 + 9, 12) if badge in ("up", "down") else (x0, 2, x0 + 8, 12)
        x_0, y_0, x_1, y_1 = box
        cx = (x_0 + x_1) // 2
        pts = {"up": [(x_0, y_1), (x_1, y_1), (cx, y_0)],
               "down": [(x_0, y_0), (x_1, y_0), (cx, y_1)]}[badge]
        d.polygon(pts, fill=255)
    font = ImageFont.truetype(BOLD, WORD_FONT_PX)
    tw = d.textlength(word, font=font)
    d.text(((w - tw) / 2, h - 2), word, font=font, fill=255, anchor="ls")
    mask = mask.point(lambda v: 255 if v >= 128 else 0)
    img = Image.new("RGBA", WORD_SIZE, (255, 255, 255, 0))
    img.putalpha(mask)
    img.save(out)


def _guarded(out: Path, name: str, make) -> None:
    f = out / name
    if f.exists():
        print(f"  {name}  <- committed asset (left as-is)")
    else:
        make(f)
        print(f"  {name}  <- drawn")


def main() -> int:
    out = HERE / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.borrow(BORROW, out)
    icon_fetch.fluent(FLUENT, out)
    for name, (base, kind) in BADGED.items():
        _guarded(out, name, lambda f, b=base, k=kind: _badge(out / b, f, k))
    for name, (base, word, badge) in WORDED.items():
        _guarded(out, name, lambda f, b=base, wd=word, k=badge: _worded(out / b, f, wd, k))
    brand_marks.ensure(out / "eclipse.png", "eclipseide")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
