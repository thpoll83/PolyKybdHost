#!/usr/bin/env python3
"""Fetch + render the TextureCraft shortcut icons (reproducible source step).

TextureCraft (github.com/storytold/texturecraft, MIT OR Apache-2.0) is the
ArtCraft suite's open-source 3D texture painting app, a Substance 3D Painter
work-alike. Its keymap is the app's OWN (the menu catalog in
`crates/ui-egui/src/menus.rs` and the engine command registry); SOURCES.md
lists every chord with file:line.

Wherever an action matches the Substance 3D Painter overlay, the glyph is the
SAME one: those icons are copied byte-identically from
`substancepainter/icons/` with `icon_fetch.borrow`; quick mask, flatten and
save-as come from `photocraft/icons/` the same way. Everything else is
Microsoft Fluent UI System Icons (MIT) via `icon_fetch`, with Material Symbols
(Apache-2.0, `ms:`) for the gaps. Camera bookmarks 1..9 are a Fluent `Video`
glyph with the digit (`../number_badge.py`).

The ESC program mark is TextureCraft's OWN icon (the engraved zebra,
`assets/app-icon/texturecraft.ico`, MIT OR Apache-2.0, 128 px frame), guarded so
a re-run never clobbers a committed `texturecraft.png`.

    PYTHONPATH=. python polyhost/res/overlay_sources/texturecraft/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import number_badge  # noqa: E402
import program_marks  # noqa: E402

# Pinned to the commit the shortcut table was read from (SOURCES.md).
TEXTURECRAFT_SHA = "42c8ea5b3c3a4cabdda03f535355cd61ac756479"
TEXTURECRAFT_ICO = ("https://raw.githubusercontent.com/storytold/texturecraft/"
                    f"{TEXTURECRAFT_SHA}/assets/app-icon/texturecraft.ico")

# Same action as the Substance 3D Painter overlay -> same art (byte-identical copy).
FROM_PAINTER = {f"{n}.png": "substancepainter" for n in (
    "hideui", "mode_bake", "mode_paint", "render", "tool_paint", "tool_eraser",
    "tool_projection", "fill", "tool_smudge", "tool_clone", "brushinc", "brushdec",
    "eyedropper", "invertgray", "material", "channel_next", "channel_prev",
    "meshmap_next", "meshmap_prev", "frame_all", "layout_3d2d", "layout_3d",
    "layout_2d", "br_mask", "mask_invert", "delete", "undo", "redo", "open",
    "save", "new", "copy", "cut", "paste", "duplicate", "group", "close", "quit",
    "export")}

# Painter's "Flatten" has no key; the PhotoCraft merge-down glyph says it.
# Quick mask is the same action as PhotoCraft's (Photoshop's) Q: its drawn glyph.
FROM_PHOTOCRAFT = {"mergedown.png": "photocraft", "saveas.png": "photocraft",
                   "quickmask.png": "photocraft"}

FLUENT = {
    "tool_path": "Bezier Curve Square",
    "tool_geomask": "Cube",
    "reimport": "Arrow Sync",
    "instantiate": "ms:dynamic_feed",
    "_camera": "Video",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(FROM_PAINTER, out)
    n += icon_fetch.borrow(FROM_PHOTOCRAFT, out)
    # Cmd/Ctrl+1..9 "Go to camera N": the digit is the information.
    n += number_badge.numbered(out / "_camera.png", "123456789", out, "camera",
                               size=0.36, centre=(0.40, 0.52))
    (out / "_camera.png").unlink()
    program_marks.own_icon(out / "texturecraft.png", TEXTURECRAFT_ICO, 128,
                           credit="storytold/texturecraft assets/app-icon/texturecraft.ico (MIT OR Apache-2.0)")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
