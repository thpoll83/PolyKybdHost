#!/usr/bin/env python3
"""Fetch + render the LightCraft shortcut icons (reproducible).

LightCraft (github.com/storytold/lightcraft, MIT OR Apache-2.0) is the ArtCraft
suite's Lightroom-like photo library and raw developer. Its keymap is its own
(crates/ui-egui/src/menus.rs, crates/engine/src/cmd/*.rs, shortcuts.rs ALIASES);
see SOURCES.md.

Glyphs: Microsoft Fluent UI System Icons (MIT, house style), Material Symbols
(Apache-2.0, `ms:` specs) for the gaps, and the Photoshop overlay's committed
drawings where the action is the same (brush size/feather, healing, gradient,
zoom 1:1, ...), copied byte-identically by `icon_fetch.borrow`.

Composites (guarded): star + digit for the 1-5 ratings, tag + digit for the
Alt+1..9 keyword-set toggles, circle + R/Y/G/B for the colour labels (a 1-bit
keycap cannot show the colour, so the initial carries it).

Program mark (ESC): LightCraft's OWN app icon (the lynx), the 128 px hicolor PNG
from assets/app-icon/ (MIT OR Apache-2.0, assets/app-icon/LICENSE.txt). Guarded.

    python polyhost/res/overlay_sources/lightcraft/fetch_icons.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from polyhost.res.overlay_sources import icon_fetch, number_badge  # noqa: E402

LC_COMMIT = "b3d392b4994ee99dc389890f006600769d0c4ff5"
MARK_URL = (f"https://raw.githubusercontent.com/storytold/lightcraft/{LC_COMMIT}/"
            "assets/app-icon/hicolor/128x128/apps/ai.storyteller.lightcraft.png")

GLYPHS = {
    # --- views ---
    "grid": "Grid",
    "detail": "Image",
    "survey": "Image Multiple",
    "filmstrip": "Filmstrip",
    "beforeafter": "Layout Column Two",
    "beforeaftersplit": "Split Vertical",
    "beforeaftertb": "Layout Row Two",
    "beforeaftersplittb": "Split Horizontal",
    "showoriginal": "History",
    "zoomtoggle": "ms:zoom_in_map",
    "zoomfit": "Zoom Fit",
    "clipping": "ms:exposure",
    "softproof": "Print",
    "maskoverlay": "Eye",
    "maskoverlayall": "ms:layers",
    "visualizespots": "ms:grain",
    "fullscreenpreview": "ms:fit_screen",
    "enterfullscreen": "Full Screen Maximize",
    "compare": "ms:compare",
    "reference": "Pin",
    "cropoverlay": "ms:grid_3x3",
    "filterbar": "Filter",
    "lightsout": "Dark Theme",
    "leftpanel": "Panel Left",
    "infooverlay": "Image Alt Text",
    "secondwindow": "Window New",
    "slideshow": "ms:slideshow",
    "done": "Checkmark",
    # --- panels / tools ---
    "editpanel": "Options",
    "masking": "ms:masks",
    "info": "Info",
    "keywords": "Tag",
    "radial": "Target",
    "presets": "Bookmark Multiple",
    "createpreset": "Bookmark Add",
    "versions": "Branch",
    "createversion": "Branch Fork",
    "guidedupright": "ms:straighten",
    "auto": "ms:auto_fix_high",
    "bw": "ms:filter_b_and_w",
    # --- edit sections ---
    "seclight": "Brightness High",
    "seccolor": "Color",
    "seceffects": "Sparkle",
    "secdetail": "ms:deblur",
    "secoptics": "Camera",
    # --- culling ---
    "pick": "Flag",
    "reject": "Dismiss Square",
    "unflag": "Flag Off",
    "clearrating": "Star Off",
    "star": "Star",
    "labelbase": "Circle",
    # --- photo / stack ---
    "settop": "Stack Star",
    "ungroup": "Group Dismiss",
    "rotateleft": "Arrow Rotate Counterclockwise",
    "rotateright": "Arrow Rotate Clockwise",
    "resetedits": "Arrow Reset",
    "resetcrop": "Crop Interim Off",
    "delete": "Delete",
    "rename": "Rename",
    "showinfinder": "Folder Open",
    "editinphotocraft": "Image Edit",
    "editexternal": "Open",
    "hdr": "ms:hdr_on",
    "hdrlast": "ms:hdr_auto",
    "panorama": "ms:panorama",
    "panoramalast": "ms:panorama_horizontal",
    # --- file / edit / app ---
    "newalbum": "Album Add",
    "newfolder": "Folder Add",
    "smartalbum": "Filter Add",
    "import": "Arrow Import",
    "export": "Share",
    "exportprevious": "Arrow Repeat All",
    "copysettings": "Copy Select",
    "pastesettings": "Clipboard Paste",
    "find": "Search",
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "selectall": "Select All On",
    "deselect": "ms:deselect",
    "quit": "Arrow Exit",
    "settings": "Settings",
    "shortcuts": "Keyboard",
    "help": "Question Circle",
    # --- navigation ---
    "prev": "Arrow Previous",
    "next": "Arrow Next",
    "up": "Arrow Up",
    "down": "Arrow Down",
}

# Same action as the Photoshop overlay: share its drawing byte-for-byte.
BORROWED = {
    "brush.png": "photoshop",
    "brushdec.png": "photoshop",
    "brushinc.png": "photoshop",
    "hardnessdec.png": "photoshop",
    "hardnessinc.png": "photoshop",
    "healing.png": "photoshop",
    "gradient.png": "photoshop",
    "eyedropper.png": "photoshop",
    "crop.png": "photoshop",
    "zoomin.png": "photoshop",
    "zoomout.png": "photoshop",
    "zoom1to1.png": "photoshop",
    "levels.png": "photoshop",
}


def _guarded_numbered(out: Path, base: str, chars: str, stem: str, **kw) -> None:
    if all((out / f"{stem}{c}.png").exists() for c in chars):
        print(f"  {stem}{chars[0]}..{stem}{chars[-1]}.png  <- committed asset (left as-is)")
        return
    number_badge.numbered(out / f"{base}.png", chars, out, stem, **kw)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)

    icon_fetch.fluent(GLYPHS, out)
    icon_fetch.borrow(BORROWED, out)

    # composites (guarded so a hand-tuned digit survives a re-run)
    _guarded_numbered(out, "star", "12345", "rate", size=40 / 96, centre=(0.50, 0.55))
    _guarded_numbered(out, "keywords", "123456789", "kw", size=36 / 96, centre=(0.40, 0.58))
    _guarded_numbered(out, "labelbase", "RYGB", "label", size=48 / 96, centre=(0.50, 0.52))

    # program mark: LightCraft's own lynx (guarded)
    mark = out / "lightcraft.png"
    if mark.exists():
        print("  lightcraft.png  <- committed asset (left as-is)")
    else:
        req = urllib.request.Request(MARK_URL, headers={"User-Agent": "polykybd"})
        mark.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        print("  lightcraft.png  <- storytold/lightcraft assets/app-icon hicolor 128px")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
