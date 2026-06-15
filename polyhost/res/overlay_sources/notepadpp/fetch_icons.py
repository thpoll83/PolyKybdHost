#!/usr/bin/env python3
"""Fetch + render the Notepad++ shortcut icons (reproducible source step).

License-clean route: **all shortcut icons come from Microsoft Fluent UI System
Icons (MIT)**, in one consistent flat style, so nothing inherits Notepad++'s
GPL-3.0 (PolyKybdHost is GPL-2.0). Line-specific glyphs are used where a generic
one would be ambiguous (e.g. "Row Triple" for duplicate-line). One icon is
custom-drawn (delete-line strike). The ESC **program icon** is the actual
Notepad++ logo (the app's own identity icon, used to mark which overlay is
loaded).

Each icon renders to a 96x96 RGBA PNG (program icon 256x256); the generator's
`luma` mode keeps the linework at 1-bit. Re-running reproduces icons/*.png.

    pip install cairosvg
    python polyhost/res/overlay_sources/notepadpp/fetch_icons.py
"""
from __future__ import annotations

import urllib.parse
import urllib.request
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw

RENDER_PX = 96
MS = "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/assets/{}"

# action filename -> Microsoft Fluent System Icon (all MIT, one consistent style).
# Line/row-specific glyphs chosen where a generic icon would mislead.
MS_ICONS = {
    "new": "Document Add/SVG/ic_fluent_document_add_24_regular.svg",
    "open": "Folder Open/SVG/ic_fluent_folder_open_24_regular.svg",
    "save": "Save/SVG/ic_fluent_save_24_regular.svg",
    "saveall": "Save Multiple/SVG/ic_fluent_save_multiple_24_regular.svg",
    "print": "Print/SVG/ic_fluent_print_24_regular.svg",
    "close": "Document Dismiss/SVG/ic_fluent_document_dismiss_24_regular.svg",
    "copy": "Copy/SVG/ic_fluent_copy_24_regular.svg",
    "cut": "Cut/SVG/ic_fluent_cut_24_regular.svg",
    "paste": "Clipboard Paste/SVG/ic_fluent_clipboard_paste_24_regular.svg",
    "undo": "Arrow Undo/SVG/ic_fluent_arrow_undo_24_regular.svg",
    "redo": "Arrow Redo/SVG/ic_fluent_arrow_redo_24_regular.svg",
    "selectall": "Select All On/SVG/ic_fluent_select_all_on_24_regular.svg",
    "duplicate": "Row Triple/SVG/ic_fluent_row_triple_24_regular.svg",
    "comment": "Comment/SVG/ic_fluent_comment_24_regular.svg",
    "find": "Search/SVG/ic_fluent_search_24_regular.svg",
    "replace": "Arrow Swap/SVG/ic_fluent_arrow_swap_24_regular.svg",
    "goto": "Arrow Down/SVG/ic_fluent_arrow_down_24_regular.svg",
    "findnext": "Chevron Right/SVG/ic_fluent_chevron_right_24_regular.svg",
    "findfiles": "Document Search/SVG/ic_fluent_document_search_24_regular.svg",
    "run": "Play/SVG/ic_fluent_play_24_regular.svg",
    "split": "Split Horizontal/SVG/ic_fluent_split_horizontal_24_regular.svg",
    "swapline": "Arrow Sort Up/SVG/ic_fluent_arrow_sort_up_24_regular.svg",
    "braces": "Braces/SVG/ic_fluent_braces_24_regular.svg",
    "join": "Text Wrap Off/SVG/ic_fluent_text_wrap_off_24_regular.svg",
    "lowercase": "Text Case Lowercase/SVG/ic_fluent_text_case_lowercase_24_regular.svg",
    "mark": "Highlight/SVG/ic_fluent_highlight_24_regular.svg",
    "top": "Arrow Circle Up/SVG/ic_fluent_arrow_circle_up_24_regular.svg",
    "bottom": "Arrow Square Down/SVG/ic_fluent_arrow_square_down_24_regular.svg",
    "nextword": "Arrow Right/SVG/ic_fluent_arrow_right_24_regular.svg",
}

# Program icon = the Notepad++ chameleon mascot logo, committed as icons/npp.png
# (a provided black-on-white line-art asset). It is NOT downloaded here so a
# re-run never clobbers it; the generator renders it via `program_icon` in
# bindings.yaml (mode: luma lights the black outlines).


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "polykybd"}), timeout=30).read()


def _draw_deleteline(path: Path) -> None:
    """Custom 'delete line' glyph: text rows + strike-through (white on transparent
    -> alpha is the shape; rendered in `mode: alpha`). A generic trash/Delete glyph
    reads as delete-*file*, so we draw the line-specific one."""
    ss = 4
    u = RENDER_PX * ss
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = int(u * 0.06)
    white = (255, 255, 255, 255)
    d.line([(u * 0.16, u * 0.26), (u * 0.60, u * 0.26)], fill=white, width=w)
    d.line([(u * 0.12, u * 0.50), (u * 0.70, u * 0.50)], fill=white, width=w)
    d.line([(u * 0.16, u * 0.74), (u * 0.50, u * 0.74)], fill=white, width=w)
    d.line([(u * 0.20, u * 0.50), (u * 0.95, u * 0.50)], fill=white, width=int(u * 0.045))
    img.resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)

    for fname, asset in MS_ICONS.items():
        enc = "/".join(urllib.parse.quote(s) for s in asset.split("/"))
        png = cairosvg.svg2png(bytestring=_get(MS.format(enc)),
                               output_width=RENDER_PX, output_height=RENDER_PX)
        (out / f"{fname}.png").write_bytes(png)
        print(f"  {fname}.png  <- ms-fluent/{asset.split('/')[0]}")

    _draw_deleteline(out / "deleteline.png")
    print("  deleteline.png  <- custom (drawn: text rows + strike-through)")

    if (out / "npp.png").exists():
        print("  npp.png  <- committed program-icon asset (left as-is)")
    else:
        print("  ! npp.png missing - add the program-icon asset to icons/")

    print(f"Wrote {len(MS_ICONS) + 1} icons to {out} (+ committed npp.png)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
