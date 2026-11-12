#!/usr/bin/env python3
"""Fetch + render the Zed shortcut icons (reproducible source step).

Four sources, in this order of preference (see SOURCES.md for every icon):

1. **Borrowed** from a sibling app folder (`icon_fetch.borrow`), byte-identical,
   wherever the action is the same as one another editor overlay already draws
   (VS Code, Sublime Text, JetBrains, Windows Terminal). Same action, same
   picture, and the overlay icon library stores it once.
2. **Microsoft Fluent UI System Icons (MIT)** — the house style — and Google
   **Material Symbols (Apache-2.0)** for the gaps (`ms:` specs).
3. **Composites** (`_badge`): a fetched glyph shrunk to the lower left with a
   small badge top right -- an up/down triangle for the previous/next member of
   a pair (next/previous diagnostic, hunk, change, occurrence...), a split pane
   for the "(split)" variant of a go-to, a plus or a cross. Zed binds many such
   pairs, and two keys of one app must not draw the same picture for different
   actions.
4. **Numbered tabs/panes** (`../number_badge.py`): Alt+1..9 (macOS Ctrl+1..9)
   activate tab N, and macOS Cmd+1..9 activate pane N -- the number IS the
   information.

The ESC **program mark is Zed's OWN app icon** (`crates/zed/resources/app-icon.png`,
part of the GPL-3.0-or-later `zed` crate; see SOURCES.md), fetched at the pinned
commit. It and every composite are guarded: a committed file is never clobbered.

Run from the repo root with the project venv:

    .venv/bin/python polyhost/res/overlay_sources/zed/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[3]))

import icon_fetch  # noqa: E402
import number_badge  # noqa: E402

ZED_COMMIT = "36682547bea1c3d4fa60c08d341cf60081853941"
ZED_ICON = (f"https://raw.githubusercontent.com/zed-industries/zed/{ZED_COMMIT}/"
            "crates/zed/resources/app-icon.png")

# Same action as another editor overlay -> the same committed drawing.
BORROW = {
    # VS Code (Fluent renders, not its reclaimed cells)
    "quickopen.png": "vscode", "gotosymbol.png": "vscode", "rename.png": "vscode",
    "definition.png": "vscode", "explorer.png": "vscode", "extensions.png": "vscode",
    "debugview.png": "vscode", "problems.png": "vscode", "terminal.png": "vscode",
    "findinfiles.png": "vscode", "replaceinfiles.png": "vscode", "sidebar.png": "vscode",
    "split.png": "vscode", "history.png": "vscode",
    # Sublime Text
    "commandpalette.png": "sublime", "gotosymbolproject.png": "sublime",
    "gotoline.png": "sublime", "reopentab.png": "sublime", "blockcomment.png": "sublime",
    "deleteline.png": "sublime", "swapup.png": "sublime", "swapdown.png": "sublime",
    "joinlines.png": "sublime", "insertafter.png": "sublime", "insertbefore.png": "sublime",
    "fold.png": "sublime", "unfold.png": "sublime", "selectline.png": "sublime",
    "multicursor.png": "sublime", "selectalloccur.png": "sublime",
    "cursorabove.png": "sublime", "cursorbelow.png": "sublime",
    "matchbracket.png": "sublime", "autocomplete.png": "sublime", "gotoword.png": "sublime",
    "duplicate.png": "sublime",
    # JetBrains (the first group are its reclaimed whole-cell drawings and are
    # bound with the same 72x40 centred geometry there and here)
    "back.png": "jetbrains", "forward.png": "jetbrains", "breakpoint.png": "jetbrains",
    "debug.png": "jetbrains", "findusages.png": "jetbrains",
    "gotodeclaration.png": "jetbrains", "gotoimpl.png": "jetbrains",
    "gototypedecl.png": "jetbrains", "reformat.png": "jetbrains",
    "stepinto.png": "jetbrains", "stepout.png": "jetbrains", "stepover.png": "jetbrains",
    "stop.png": "jetbrains",
    "extendselection.png": "jetbrains", "shrinkselection.png": "jetbrains",
    "optimizeimports.png": "jetbrains", "paraminfo.png": "jetbrains",
    "intentions.png": "jetbrains", "rerun.png": "jetbrains", "win_git.png": "jetbrains",
    # Windows Terminal
    "newwindow.png": "windowsterminal", "settingsfile.png": "windowsterminal",
    "tab.png": "windowsterminal",
}

FLUENT = {
    "saveall": "Save Multiple",
    "openremote": "Cloud",
    "openremotehere": "Cloud Link",
    "hideothers": "Window Multiple",
    "appmenu": "Navigation",
    "trust": "Shield",
    "settingsprofile": "Person Settings",
    "tabswitcher": "Tabs",
    "focusnext": "Arrow Next",
    "focusprev": "Arrow Previous",
    "whichkey": "Keyboard",
    "toastaction": "Alert",
    "branches": "Branch",
    "worktree": "Branch Fork",
    "closeinactive": "Dismiss Square Multiple",
    "tabmoveleft": "Tab Desktop Arrow Left",
    "rightdock": "Panel Right",
    "bottomdock": "Panel Bottom",
    "alldocks": "Board",
    "closedock": "Panel Bottom Contract",
    "dockgrow": "Panel Right Expand",
    "dockshrink": "Panel Right Contract",
    "dockreset": "Arrow Reset",
    "docksgrow": "Arrow Maximize",
    "docksshrink": "Arrow Minimize",
    "docksreset": "Arrow Sync",
    "outlinepanel": "Text Bullet List",
    "collab": "People Team",
    "agent": "Bot",
    "agentadd": "Bot Add",
    "wssidebar": "Panel Left Text",
    "wssidebarfocus": "Panel Left Header",
    "follow": "Person Arrow Right",
    "cursornames": "Person Tag",
    "findinselection": "Select Object",
    "usesel": "ms:manage_search",
    "matchcase": "Text Case Title",
    "wholeword": "Text Whole Word",
    "regex": "ms:regular_expression",
    "togglereplace": "ms:swap_horiz",
    "filters": "Filter",
    "textfinder": "Search Square",
    "undosel": "Arrow Hook Up Left",
    "redosel": "Arrow Hook Up Right",
    "emoji": "Emoji",
    "contextmenu": "More Vertical",
    "enclosingsymbol": "Code Block",
    "multibuffer": "Stack",
    "lsp": "Server",
    "predictmenu": "Sparkle",
    "predicttoggle": "Sparkle Circle",
    "predictrate": "Thumb Like",
    "hunk": "ms:difference",
    "hunkexpand": "ms:unfold_more",
    "linenumbers": "ms:format_list_numbered",
    "taskspawn": "Play",
    "taskspawncenter": "Play Circle",
    "rerunsame": "Arrow Repeat All",
    "debugrerun": "Bug Arrow Counterclockwise",
    "logbreakpoint": "Note Edit",
    # bases for the composites below (underscore = not bound directly)
    "_window": "Window",
    "_search": "Search",
    "_code": "Code",
    "_warning": "Warning",
    "_edit": "Edit",
    "_targetarrow": "Target Arrow",
    "_cube": "Cube",
    "_tab": "Tab",
}

# composite -> (base file, badge)
BADGED = {
    "closewindow.png": ("_window.png", "x"),
    "closeothers.png": ("tabswitcher.png", "x"),
    "tabswitcherlast.png": ("tabswitcher.png", "up"),
    "nexttab.png": ("_tab.png", "right"),
    "prevtab.png": ("_tab.png", "left"),
    "newterminal.png": ("terminal.png", "plus"),
    "findprev.png": ("_search.png", "up"),
    "dupup.png": ("duplicate.png", "up"),
    "dupdown.png": ("duplicate.png", "down"),
    "multicursorprev.png": ("multicursor.png", "up"),
    "nodenext.png": ("_code.png", "down"),
    "nodeprev.png": ("_code.png", "up"),
    "definitionsplit.png": ("definition.png", "split"),
    "declarationsplit.png": ("_targetarrow.png", "split"),
    "typedefsplit.png": ("_cube.png", "split"),
    "diagnext.png": ("_warning.png", "down"),
    "diagprev.png": ("_warning.png", "up"),
    "hunknext.png": ("hunk.png", "down"),
    "hunkprev.png": ("hunk.png", "up"),
    "changenext.png": ("_edit.png", "down"),
    "changeprev.png": ("_edit.png", "up"),
}

INK = (0, 0, 0, 255)


def _badge(base: Path, out: Path, kind: str) -> None:
    """`base` shrunk into the lower-left 72% of a 96px canvas + a badge top right.

    Drawn at 4x and downsampled, like the other shared marks. Opaque pixels are
    what the `alpha` mode lights, so the ink colour does not matter."""
    s = 4
    u = 96 * s
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    g = Image.open(base).convert("RGBA").resize((int(u * 0.72), int(u * 0.72)), Image.LANCZOS)
    img.alpha_composite(g, (0, u - g.height))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = int(u * 0.70), 0, u - 1, int(u * 0.30)
    w = int(u * 0.045)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    if kind == "up":
        d.polygon([(x0, y1), (x1, y1), (cx, y0)], fill=INK)
    elif kind == "down":
        d.polygon([(x0, y0), (x1, y0), (cx, y1)], fill=INK)
    elif kind == "right":
        d.polygon([(x0, y0), (x0, y1), (x1, cy)], fill=INK)
    elif kind == "left":
        d.polygon([(x1, y0), (x1, y1), (x0, cy)], fill=INK)
    elif kind == "x":
        d.line([(x0, y0), (x1, y1)], fill=INK, width=w)
        d.line([(x0, y1), (x1, y0)], fill=INK, width=w)
    elif kind == "plus":
        d.line([(cx, y0), (cx, y1)], fill=INK, width=w)
        d.line([(x0, cy), (x1, cy)], fill=INK, width=w)
    elif kind == "split":
        d.rectangle([x0, y0 + w // 2, x1, y1], outline=INK, width=w)
        d.line([(cx, y0), (cx, y1)], fill=INK, width=w)
    else:
        raise ValueError(kind)
    img.resize((96, 96), Image.LANCZOS).save(out)


def _mirror(src: Path, out: Path) -> None:
    Image.open(src).transpose(Image.FLIP_LEFT_RIGHT).save(out)


def _last_tab(base: Path, out: Path) -> None:
    """Tab glyph with '»' inside: Alt+0 (macOS Ctrl+0) = last tab. Same font,
    size and centre as number_badge, so it reads as one family with tab1..tab9."""
    img = Image.open(base).convert("RGBA")
    px = img.width
    font = ImageFont.truetype(number_badge.BOLD, int(px * 52 / 96))
    ImageDraw.Draw(img).text((px * 0.50, px * 0.56), "»", fill=INK, font=font, anchor="mm")
    img.save(out)


def _guarded(out: Path, name: str, make) -> None:
    f = out / name
    if f.exists():
        print(f"  {name}  <- committed asset (left as-is)")
    else:
        make(f)
        print(f"  {name}  <- drawn")


def _zed_mark(path: Path) -> None:
    """Zed's own 512px app icon, cropped to its light linework + 12% padding.

    The icon is a dark rounded tile carrying a light Z-in-frames mark; the
    tile's own padding would shrink the mark to ~22 px on a 40 px keycap, so the
    crop keeps only the mark (bbox of pixels with alpha-weighted luma > 110).
    Rendered with `program_icon_mode: bright`: it lights the light linework and
    leaves the dark tile unlit (`alpha` lights the whole tile as one blob)."""
    import numpy as np
    with urllib.request.urlopen(ZED_ICON, timeout=60) as r:
        data = r.read()
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    a = np.asarray(im).astype(float)
    lum = a[..., :3].mean(-1) * a[..., 3] / 255
    ys, xs = np.where(lum > 110)
    p = int(max(xs.max() - xs.min(), ys.max() - ys.min()) * 0.12)
    im.crop((xs.min() - p, ys.min() - p, xs.max() + p, ys.max() + p)).save(path)


def main() -> int:
    out = HERE / "icons"
    out.mkdir(exist_ok=True)
    n = icon_fetch.borrow(BORROW, out)
    n += icon_fetch.fluent(FLUENT, out)
    for name, (base, kind) in BADGED.items():
        _guarded(out, name, lambda f, b=base, k=kind: _badge(out / b, f, k))
    _guarded(out, "tabmoveright.png", lambda f: _mirror(out / "tabmoveleft.png", f))
    _guarded(out, "tablast.png", lambda f: _last_tab(out / "tab.png", f))
    n += len(BADGED) + 2
    # Alt+1..9 -> tab N (numbers over Windows Terminal's tab glyph, same family)
    n += number_badge.numbered(out / "tab.png", "123456789", out, "tab")
    # macOS Cmd+1..9 -> pane N
    n += number_badge.numbered(out / "_window.png", "123456789", out, "pane",
                               centre=(0.50, 0.60))
    _guarded(out, "zed.png", _zed_mark)
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
