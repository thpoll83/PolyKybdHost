#!/usr/bin/env python3
"""Fetch + render the AniCraft shortcut icons (reproducible source step).

AniCraft (github.com/storytold/anicraft, MIT OR Apache-2.0) is the ArtCraft
suite's open-source 2D vector animation editor, an Adobe Animate work-alike.
Its keymap is the app's OWN (the engine command registry, `Tool::shortcut` and
`VIEW_SHORTCUTS`); SOURCES.md lists every chord with file:line.

Style: Microsoft Fluent UI System Icons (MIT) via `icon_fetch`, the house
style, with Material Symbols (Apache-2.0, `ms:`) for gaps. Drawing tools that
VectorCraft (the Illustrator work-alike of the same suite) also has are COPIED
from `vectorcraft/icons/`, so the same tool draws the same cell; the brush-size
and paint-bucket glyphs come from `photocraft/icons/`, and the frame-step and
first/last-frame glyphs from `effectcraft/` and `soundcraft/`.

Drawn here (no stock glyph says it): the timeline frame cells (insert frame,
remove frame, keyframe, blank keyframe, clear keyframe).

The ESC program mark is AniCraft's OWN icon (the engraved rabbit,
`assets/app-icon/anicraft.ico`, MIT OR Apache-2.0, 128 px frame), guarded so a
re-run never clobbers a committed `anicraft.png`.

    PYTHONPATH=. python polyhost/res/overlay_sources/anicraft/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import program_marks  # noqa: E402

# Pinned to the commit the shortcut table was read from (SOURCES.md).
ANICRAFT_SHA = "9e49ae93a7ee167f19e0b7035eb3ebed0ccbe805"
ANICRAFT_ICO = ("https://raw.githubusercontent.com/storytold/anicraft/"
                f"{ANICRAFT_SHA}/assets/app-icon/anicraft.ico")

# Same tool or action as a sibling ArtCraft set -> same art (byte-identical copy).
BORROWED = {
    **{f"{n}.png": "vectorcraft" for n in (
        "select", "directselect", "freetransform", "width", "pen", "type",
        "pencil", "paintbrush", "blobbrush", "eraser", "rectangle", "ellipse",
        "line", "eyedropper", "hand", "zoom", "new", "open", "save", "saveas",
        "undo", "redo", "cut", "copy", "paste", "pasteinplace", "selectall",
        "deselect", "clear", "bringforward", "sendbackward", "tofront", "toback",
        "zoomin", "zoomout", "fitall", "actualsize", "place", "snaptopoint",
        "prefs", "quit")},
    **{f"{n}.png": "photocraft" for n in ("brushdec", "brushinc", "fill")},
    **{f"{n}.png": "effectcraft" for n in ("prevframe", "nextframe")},
    **{f"{n}.png": "soundcraft" for n in ("rtz", "goend", "play")},
}

FLUENT = {
    # tools
    "bone": "ms:polyline",
    "inkbottle": "ms:border_color",
    "camera": "Video",
    "objectdrawing": "ms:format_shapes",
    # timeline / control
    "testmovie": "Play Circle",
    "prevscene": "Arrow Previous",
    "nextscene": "Arrow Next",
    "onion": "ms:auto_awesome_motion",
    "selectallframes": "ms:view_week",
    "cutframes": "ms:content_cut",
    "copyframes": "ms:content_copy",
    "pasteframes": "ms:content_paste",
    # modify
    "breakapart": "Group Dismiss",
    "duplicate": "Copy Add",
    "editsymbol": "ms:interests",
    "convertsymbol": "ms:library_add",
    "removetransform": "Arrow Reset",
    "rotateccw": "Arrow Rotate Counterclockwise",
    "rotatecw": "Arrow Rotate Clockwise",
    "shapehint": "ms:add_location",
    "alignleft": "ms:align_horizontal_left",
    "alignhcenter": "ms:align_horizontal_center",
    "alignright": "ms:align_horizontal_right",
    "aligntop": "ms:align_vertical_top",
    "alignvcenter": "ms:align_vertical_center",
    "alignbottom": "ms:align_vertical_bottom",
    "aligntostage": "ms:filter_center_focus",
    # file / window / help
    "publish": "Arrow Export",
    "publishsettings": "ms:settings_applications",
    "search": "Search",
    "findnext": "Chevron Down",
    "findprev": "Chevron Up",
    "movieexplorer": "Text Bullet List Tree",
    "actions": "Code",
    "nextpanel": "ms:keyboard_tab",
    "prevpanel": "ms:keyboard_tab_rtl",
    "commandpalette": "Apps List Detail",
    "shortcuts": "Keyboard",
}

PX, SS = 96, 4
WHITE = (255, 255, 255, 255)


def _cell(path: Path, kind: str) -> None:
    """A timeline frame cell with its mark: white on transparent -> mode alpha."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    u = PX * SS
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = int(u * 0.075)
    x0, y0, x1, y1 = int(u * .24), int(u * .08), int(u * .76), int(u * .92)
    d.rectangle([x0, y0, x1, y1], outline=WHITE, width=w)
    cx, cy, r = u // 2, int(u * .62), int(u * .15)
    if kind in ("key", "clear"):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)
    if kind == "blank":
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=WHITE, width=w)
    if kind == "clear":
        d.line([(x0, y1), (x1, y0)], fill=WHITE, width=w)
    if kind in ("add", "remove"):
        a = int(u * .15)
        cy = u // 2
        d.rectangle([cx - a, cy - w // 2, cx + a, cy + w // 2], fill=WHITE)
        if kind == "add":
            d.rectangle([cx - w // 2, cy - a, cx + w // 2, cy + a], fill=WHITE)
    img.resize((PX, PX), Image.LANCZOS).save(path)
    print(f"  {path.name}  <- drawn frame cell ({kind})")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROWED, out)
    for name, kind in (("insertframe", "add"), ("removeframe", "remove"), ("keyframe", "key"),
                       ("blankkeyframe", "blank"), ("clearkeyframe", "clear")):
        _cell(out / f"{name}.png", kind)
    program_marks.own_icon(out / "anicraft.png", ANICRAFT_ICO, 128,
                           credit="storytold/anicraft assets/app-icon/anicraft.ico (MIT OR Apache-2.0)")
    # The ESC mark: the icon's animal as one solid shape at keycap size, with its
    # darkest lines cut back out (program_marks.silhouette_mark).
    program_marks.silhouette_mark(out / "anicraft_mark.png", out / "anicraft.png", cut=120)
    print(f"Wrote {n} icons (+ frame cells, program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
