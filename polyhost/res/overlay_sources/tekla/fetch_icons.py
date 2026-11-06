#!/usr/bin/env python3
"""Fetch + render the Tekla Structures shortcut icons (reproducible).

Glyphs: Material Symbols (Apache-2.0) through `ms:` names and Microsoft Fluent
UI System Icons (MIT). An action that another CAD set already draws uses that
set's file, copied byte for byte (`BORROW`, `BORROW_AS`), so one action has one
glyph in every CAD set.

Drawn here, 32x32 at 1 bit (black on transparent, so the spec's `luma` mode
lights the black pixels and the generator places them 1:1):

* the four rendering modes (wireframe, shaded wireframe, grayscale, rendered)
  as one isometric cube with the faces empty, light, dithered and solid;
* the coordinate locks: the letter X, Y or Z beside a padlock;
* the view-mode keys: each mode cube (and the "only selected" checkbox) with
  a corner letter for the objects the key acts on: P parts (Ctrl), C
  components (Shift), R references (Ctrl+Shift), B building hierarchy
  (Ctrl+Alt).

The ESC mark is the Tekla logo from tekla.com's favicon, fitted into 32x32 and
reduced to 1 bit (dark pixels lit), white on transparent for
`program_icon_mode: alpha`. It is guarded: a committed tekla.png is left as it
is, and so is every drawn icon.

    pip install cairosvg Pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/tekla/fetch_icons.py
"""
from __future__ import annotations

import io
import shutil
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

HERE = Path(__file__).resolve().parent
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Tekla's favicon: the Tekla mark (two blue parallelograms and a triangle).
MARK_URL = "https://www.google.com/s2/favicons?domain=tekla.com&sz=256"
MARK_PX = 32
MARK_DARK_LUMA = 170   # pixels darker than this (the blue mark) are lit

FLUENT = {
    # --- common ---
    "ctxtoolbar": "ms:toolbar",            # same spec as fusion navbar
    "directmod": "ms:touch_app",
    "quicklaunch": "ms:rocket_launch",
    "catalog": "ms:apps",
    "shortcutsdlg": "ms:keyboard",
    # AutoCAD's ortho glyph (four arrows) is the same picture as Move here.
    "ortho": "ms:square_foot",
    # --- rendering ---
    "onlyselected": "ms:select_check_box",
    # --- selecting ---
    "rollover": "ms:highlight_mouse_cursor",
    "selswitchall": "ms:select_all",
    "selswitchparts": "ms:deployed_code",
    "selrebarsets": "ms:view_headline",
    "selrebargroups": "ms:density_medium",
    "selrebarsingle": "ms:remove",
    "hideobject": "Eye Off",
    # --- snapping ---
    "snapref": "ms:my_location",
    "snapgeom": "ms:polyline",
    "snapnear": "ms:near_me",
    "snapany": "ms:point_scan",
    "coordrel": "ms:moved_location",
    "coordabs": "ms:location_on",
    "coordglobal": "ms:public",
    "snapnext": "ms:keyboard_tab",
    "snapprev": "ms:keyboard_tab_rtl",
    # --- copying and moving ---
    "smartselect": "ms:ads_click",
    "copyprops": "ms:copy_all",
    "pasteprops": "ms:content_paste_go",
    # --- viewing ---
    "modelviews": "ms:view_carousel",
    "zoomprev": "ms:youtube_searched_for",
    "rotpoint": "ms:center_focus_weak",
    "rotcont": "ms:autorenew",
    "rotswitch": "ms:screen_rotation_alt",
    "mousepan": "ms:mouse",
    "centercursor": "ms:filter_center_focus",
    "fly": "ms:flight",
    "clipplane": "ms:crop",
    "viewleft": "ms:arrow_back",
    "viewright": "ms:arrow_forward",
    "viewup": "ms:arrow_upward",
    "viewdown": "ms:arrow_downward",
    # --- checking ---
    "inquire": "ms:info",
    "report": "ms:summarize",
    "phases": "ms:view_timeline",
    "autoconn": "ms:hub",
    "docmanager": "ms:folder_managed",
    # --- rebar display ---
    "legface": "ms:square",
    "guideline": "ms:line_axis",
    "propmod": "ms:tune",
    "splitter": "ms:call_split",
    "enddetail": "ms:line_end",
    "rebarcolors": "ms:palette",
    # --- part position ---
    "partup": "ms:keyboard_double_arrow_up",
    "partdown": "ms:keyboard_double_arrow_down",
    "partleft": "ms:keyboard_double_arrow_left",
    "partright": "ms:keyboard_double_arrow_right",
    "partrot90": "ms:rotate_90_degrees_cw",
}

# Same action, same file name as another CAD set: byte-identical copies.
BORROW = {
    "properties.png": "autocad",
    "repeatcmd.png": "autocad",
    "selprev.png": "autocad",
    "quickselect.png": "autocad",
    "move.png": "fusion",
    "measure.png": "fusion",
    "preferences.png": "freecad",
    "home.png": "freecad",
    "boxzoom.png": "freecad",
    "fullscreen.png": "freecad",
    "isometric.png": "freecad",
    "nextwin.png": "freecad",
    "refresh.png": "freecad",
    "rotright.png": "freecad",
    "orbit.png": "effectcraft",
    "hand.png": "photoshop",
}

# Same glyph as another set under another file name: {ours: (app, theirs)}.
BORROW_AS = {
    "rebardim.png": ("fusion", "dimension.png"),
}

LIT = (0, 0, 0, 255)
CLEAR = (0, 0, 0, 0)


def _borrow_as(out: Path) -> int:
    for name, (app, src) in sorted(BORROW_AS.items()):
        dest = out / name
        if dest.exists():
            print(f"  {name}  <- committed asset (left as-is)")
        else:
            shutil.copyfile(HERE.parent / app / "icons" / src, dest)
            print(f"  {name}  <- copied from {app}/icons/{src}")
    return len(BORROW_AS)


# The cube: three faces of an isometric box in a 32x32 cell.
TOP = [(16, 1), (30, 8), (16, 15), (2, 8)]
LEFT = [(2, 8), (16, 15), (16, 30), (2, 23)]
RIGHT = [(16, 15), (30, 8), (30, 23), (16, 30)]
EDGES = [((16, 1), (30, 8)), ((30, 8), (30, 23)), ((30, 23), (16, 30)),
         ((16, 30), (2, 23)), ((2, 23), (2, 8)), ((2, 8), (16, 1)),
         ((2, 8), (16, 15)), ((30, 8), (16, 15)), ((16, 15), (16, 30))]


def _face(img: Image.Image, poly, every: int) -> None:
    """Light every `every`-th pixel of a face on a diagonal grid (0 = none,
    1 = all), so the faces read as different shades at 1 bit."""
    if every == 0:
        return
    mask = Image.new("1", img.size, 0)
    ImageDraw.Draw(mask).polygon(poly, fill=1)
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            if mask.getpixel((x, y)) and (x + y) % every == 0:
                px[x, y] = LIT


def _cube(path: Path, faces: tuple[int, int, int], cut_edges: bool) -> None:
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    img = Image.new("RGBA", (32, 32), CLEAR)
    for poly, every in zip((TOP, LEFT, RIGHT), faces):
        _face(img, poly, every)
    d = ImageDraw.Draw(img)
    if cut_edges:
        # Solid faces: the inner edges are cut out so the three faces separate.
        for a, b in EDGES[6:]:
            d.line([a, b], fill=CLEAR, width=2)
    else:
        for a, b in EDGES:
            d.line([a, b], fill=LIT, width=2)
    img.save(path)
    print(f"  {path.name}  <- drawn cube {faces}")


def _lock(path: Path, letter: str) -> None:
    """The axis letter on the left, a padlock on the right (36x32)."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    img = Image.new("RGBA", (36, 32), CLEAR)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(BOLD, 22)
    box = d.textbbox((0, 0), letter, font=f)
    d.text((1 - box[0], 31 - box[3]), letter, font=f, fill=LIT)
    # padlock: shackle (two posts and a top bar) and a solid body with a keyhole
    d.rectangle([22, 14, 34, 31], fill=LIT)
    d.rectangle([27, 19, 29, 25], fill=CLEAR)
    d.rectangle([23, 6, 25, 13], fill=LIT)
    d.rectangle([31, 6, 33, 13], fill=LIT)
    d.rectangle([23, 4, 33, 6], fill=LIT)
    img.save(path)
    print(f"  {path.name}  <- drawn lock '{letter}'")


def _mark(path: Path) -> None:
    """The Tekla favicon contain-fitted into MARK_PX square, dark pixels lit."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    req = urllib.request.Request(MARK_URL, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read())).convert("RGBA")
    icon = icon.crop(icon.getbbox())
    side = max(icon.size)
    square = Image.new("RGBA", (side, side), (255, 255, 255, 0))
    square.alpha_composite(icon, ((side - icon.width) // 2, (side - icon.height) // 2))
    white = Image.new("RGBA", square.size, "white")
    white.alpha_composite(square)
    a = white.convert("L").resize((MARK_PX, MARK_PX), Image.LANCZOS).point(
        lambda v: 255 if v < MARK_DARK_LUMA else 0)
    Image.merge("RGBA", (a, a, a, a)).save(path)
    print(f"  {path.name}  <- Tekla favicon, 1-bit, dark pixels lit")


# The view-mode keys repeat the same five modes for parts (Ctrl), components
# (Shift), references (Ctrl+Shift) and the building hierarchy (Ctrl+Alt). The
# letter in the bottom-right corner says which objects the key acts on.
BADGES = {"p": "P", "c": "C", "r": "R", "b": "B"}
BADGED = ("wireframe", "shadedwire", "grayscale", "rendered", "onlyselected")


def _badged(out: Path, base: str, key: str) -> None:
    """`base` (fitted into 32x32 on the left) with the letter BADGES[key] in
    the bottom-right corner of a 40x32 cell, black on transparent."""
    path = out / f"{base}_{key}.png"
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    src = Image.open(out / f"{base}.png").convert("RGBA")
    if src.size != (32, 32):
        src = src.resize((32, 32), Image.LANCZOS)
    mask = Image.new("L", (40, 32), 0)
    mask.paste(src.getchannel("A").point(lambda v: 255 if v > 100 else 0), (0, 0))
    d = ImageDraw.Draw(mask)
    font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 13)
    letter = BADGES[key]
    d.text((40 - d.textlength(letter, font=font), 32), letter, font=font, fill=255, anchor="ls")
    mask = mask.point(lambda v: 255 if v >= 128 else 0)
    img = Image.new("RGBA", (40, 32), CLEAR)
    img.paste(Image.new("RGBA", (40, 32), LIT), (0, 0), mask)
    img.save(path)
    print(f"  {path.name}  <- drawn: {base} + '{letter}'")


def main() -> int:
    out = HERE / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    n += _borrow_as(out)
    _cube(out / "wireframe.png", (0, 0, 0), False)
    _cube(out / "shadedwire.png", (4, 4, 4), False)
    _cube(out / "grayscale.png", (4, 3, 2), False)
    _cube(out / "rendered.png", (1, 1, 1), True)
    for base in BADGED:
        for key in BADGES:
            # Tekla has only wireframe and shaded wireframe for the hierarchy.
            if key != "b" or base in ("wireframe", "shadedwire"):
                _badged(out, base, key)
    for axis in "XYZ":
        _lock(out / f"lock{axis.lower()}.png", axis)
    _mark(out / "tekla.png")
    print(f"Wrote {n} icons (+ 7 drawn and the program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
