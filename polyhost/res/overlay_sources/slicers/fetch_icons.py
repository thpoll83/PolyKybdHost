#!/usr/bin/env python3
"""Fetch + render the slicer shortcut icons (PrusaSlicer, Bambu Studio, OrcaSlicer).

The three apps share one icon folder because they share one shortcut set by
descent; `keys.yaml` names the icon of each binding.

* Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
  (Apache-2.0) where `FLUENT` names `ms:<name>`.
* A family of actions that differs by one word (camera views, the painting
  gizmos, the arrow-key move steps, filament and favourite numbers) is a
  composite: a glyph above a short word, drawn 1-bit at 40x40
  (`composites()`), bound with `region: [40, 40]` and `mode: alpha`.
* The filament spool (`spool()`) and the brim ears (`brim_ears()`) are drawn
  here; neither icon set has them.
* ESC marks: Bambu Lab's logo from Simple Icons (CC0 artwork, nominative use,
  see `../brand_marks.py`). Simple Icons has no PrusaSlicer or OrcaSlicer mark,
  and the apps' own icons are AGPL-3.0 artwork that is not committed here, so
  those two are drawn letter tiles (`letter_tile()`).

Every drawn file is skipped when it exists, so a hand-tuned PNG survives a
re-run. Fluent and Material downloads are deterministic and re-fetch freely.

    pip install cairosvg
    python polyhost/res/overlay_sources/slicers/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

FLUENT = {
    # project / files
    "new_project": "Document Add",
    "import_model": "Cube Add",
    "import_config": "Document Arrow Left",
    "merge_config": "Merge",
    "export_config": "Document Arrow Right",
    "export_gcode": "ms:download",
    "send_gcode": "Cloud Arrow Up",
    "print": "Print",
    "sd_card": "ms:sd_card",
    "eject": "ms:eject",
    "publish": "ms:publish",
    "host_queue": "Text Bullet List Square",
    "new_instance": "Window New",
    "slice": "ms:stacks",
    # editing
    "delete_all": "ms:delete_sweep",
    "clone": "Square Multiple",
    "reload": "Arrow Clockwise",
    "reload_device": "Arrow Sync",
    "search": "Search",
    "select_plates": "Select All On",
    # tabs / view
    "tab_plater": "Home",
    "tab_print": "ms:tune",
    "tab_printer": "Print",
    "view_3d": "ms:view_in_ar",
    "preview": "Eye",
    "switch_view": "Arrow Swap",
    "sidebar": "Panel Right Contract",
    "next_tab": "Arrow Next",
    "prev_tab": "Arrow Previous",
    "window_reset": "ms:view_compact",
    "labels": "Tag",
    "layer_labels": "Tag Multiple",
    "overhang": "ms:roofing",
    "collision": "ms:deployed_code_alert",
    "wireframe": "ms:change_history",
    "camera_type": "Camera Switch",
    "zoom_bed": "ms:fit_screen",
    "zoom_fit": "Zoom Fit",
    "mouse3d": "ms:joystick",
    "shortcuts": "Keyboard",
    "speed_dial": "ms:speed",
    # objects / placement
    "arrange": "ms:grid_view",
    "arrange_sel": "ms:dashboard_customize",
    "orient": "ms:explore",
    "add_instance": "Add Square",
    "remove_instance": "Subtract Square",
    "printable": "ms:print_disabled",
    "rotate_ccw": "Arrow Rotate Counterclockwise",
    "rotate_cw": "Arrow Rotate Clockwise",
    # gizmos
    "gizmo_move": "Arrow Move",
    "gizmo_scale": "Arrow Maximize",
    "gizmo_rotate": "ms:3d_rotation",
    "gizmo_cut": "Split Vertical",
    "gizmo_face": "ms:vertical_align_bottom",
    "gizmo_fuzzy": "ms:grain",
    "gizmo_text": "ms:text_fields",
    "gizmo_boolean": "ms:join_inner",
    "gizmo_measure": "ms:straighten",
    "gizmo_assembly": "Puzzle Piece",
    # G-code viewer
    "layer_up": "Chevron Double Up",
    "layer_down": "Chevron Double Down",
    "move_back": "Previous",
    "move_fwd": "Next",
    "one_layer": "ms:filter_1",
    "legend": "ms:legend_toggle",
    "gcode_window": "Code",
}

# Glyphs used only as the top half of a composite; not bound directly.
PARTS = {
    "_cube": "Cube",
    "_brush": "Paint Brush",
    "_star": "Star",
    "_up": "Arrow Up",
    "_down": "Arrow Down",
    "_left": "Arrow Left",
    "_right": "Arrow Right",
}

# file stem -> (glyph, word under it)
COMPOSITES = {
    # camera views: Prusa 0-6, Bambu and Orca Ctrl+0-7
    "view_iso": ("_cube", "ISO"),
    "view_top": ("_cube", "TOP"),
    "view_bottom": ("_cube", "BOT"),
    "view_front": ("_cube", "FRNT"),
    "view_rear": ("_cube", "REAR"),
    "view_left": ("_cube", "LEFT"),
    "view_right": ("_cube", "RGHT"),
    "view_default": ("_cube", "DEF"),
    "view_plate": ("_cube", "PLAT"),
    # painting gizmos
    "paint_supports": ("_brush", "SUP"),
    "paint_seam": ("_brush", "SEAM"),
    "paint_mmu": ("_brush", "MMU"),
    "paint_texture": ("_brush", "TEX"),
    # arrow keys: 10 mm step, Shift = 1 mm step, Ctrl = camera space
    **{f"move_{d}_{s}": (f"_{d}", w)
       for d in ("up", "down", "left", "right")
       for s, w in (("10", "10mm"), ("1", "1mm"), ("cam", "VIEW"))},
    # OrcaSlicer Alt+1..9, 0: run favourite 1..10
    **{f"fav_{n}": ("_star", str(n)) for n in range(1, 11)},
}

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
SIZE = 40          # composites are drawn 1:1 at the bound region
GLYPH_H = 24       # height of the glyph above the word
TEXT_PX = 13       # one static size for every word, so a family reads as a set
BASELINE = 38


def _mask(path: Path) -> Image.Image:
    """The glyph's alpha, cropped to its ink."""
    a = Image.open(path).convert("RGBA").split()[3]
    return a.crop(a.getbbox())


def _save_1bit(mask: Image.Image, dest: Path) -> None:
    mask = mask.point(lambda v: 255 if v >= 128 else 0)
    img = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    img.putalpha(mask)
    img.save(dest)


def composites(out: Path, parts: Path) -> None:
    """Glyph above a word, 1-bit, white on transparent."""
    font = None
    for stem, (glyph, word) in COMPOSITES.items():
        dest = out / f"{stem}.png"
        if dest.exists():
            print(f"  {dest.name}  <- committed asset (left as-is)")
            continue
        font = font or ImageFont.truetype(BOLD, TEXT_PX)
        g = _mask(parts / f"{glyph}.png")
        g = g.resize((round(g.width * GLYPH_H / g.height), GLYPH_H), Image.LANCZOS)
        mask = Image.new("L", (SIZE, SIZE), 0)
        mask.paste(g, ((SIZE - g.width) // 2, 0))
        d = ImageDraw.Draw(mask)
        w = d.textlength(word, font=font)
        d.text(((SIZE - w) / 2, BASELINE), word, font=font, fill=255, anchor="ls")
        _save_1bit(mask, dest)
        print(f"  {dest.name}  <- composite ({glyph} + '{word}')")


def _spool(mask: Image.Image, x0: int, y0: int, w: int, h: int) -> None:
    """A filament spool seen from the side: two flanges and the wound
    filament between them as diagonal hatching."""
    fl = 4                                   # flange width
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([x0, y0, x0 + fl, y0 + h], radius=1, fill=255)
    d.rounded_rectangle([x0 + w - fl, y0, x0 + w, y0 + h], radius=1, fill=255)
    core = Image.new("L", (w, h), 0)
    cd = ImageDraw.Draw(core)
    for k in range(-h, w + h, 5):
        cd.line([(k, h), (k + h // 2, 0)], fill=255, width=2)
    clip = Image.new("L", (w, h), 0)
    ImageDraw.Draw(clip).rectangle([fl + 1, 3, w - fl - 1, h - 3], fill=255)
    mask.paste(core, (x0, y0), clip)


def spool(out: Path) -> None:
    """`spool.png` (filament settings) and `filament_<n>.png` (spool + digit)."""
    dest = out / "spool.png"
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
    else:
        mask = Image.new("L", (SIZE, SIZE), 0)
        _spool(mask, 6, 4, 28, 32)
        _save_1bit(mask, dest)
        print(f"  {dest.name}  <- drawn spool")
    font = None
    for n in range(1, 10):
        dest = out / f"filament_{n}.png"
        if dest.exists():
            print(f"  {dest.name}  <- committed asset (left as-is)")
            continue
        font = font or ImageFont.truetype(BOLD, TEXT_PX)
        mask = Image.new("L", (SIZE, SIZE), 0)
        _spool(mask, 9, 0, 22, GLYPH_H)
        d = ImageDraw.Draw(mask)
        w = d.textlength(str(n), font=font)
        d.text(((SIZE - w) / 2, BASELINE), str(n), font=font, fill=255, anchor="ls")
        _save_1bit(mask, dest)
        print(f"  {dest.name}  <- drawn spool + '{n}'")


def brim_ears(out: Path) -> None:
    """`brim_ears.png`: an object's footprint with a brim ear (disc) on each
    corner, as the gizmo places them. Neither icon set has one."""
    dest = out / "brim_ears.png"
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    mask = Image.new("L", (SIZE, SIZE), 0)
    d = ImageDraw.Draw(mask)
    for cx, cy in ((9, 9), (31, 9), (9, 31), (31, 31)):
        d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], outline=255, width=2)
    d.rectangle([9, 9, 31, 31], fill=0)
    d.rectangle([9, 9, 31, 31], outline=255, width=3)
    _save_1bit(mask, dest)
    print(f"  {dest.name}  <- drawn footprint + ears")


def letter_tile(dest: Path, letter: str) -> None:
    """ESC mark: a filled rounded tile with `letter` and three print layers
    knocked out, 1-bit at the bound region (37x32)."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    w, h = 37, 32
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=6, fill=255)
    font = ImageFont.truetype(BOLD, 21)
    box = d.textbbox((0, 0), letter, font=font)
    d.text(((w - (box[2] - box[0])) / 2 - box[0], 3 - box[1]), letter, font=font, fill=0)
    for y in (24, 27):                       # two layer lines under the letter
        d.rectangle([6, y, w - 7, y + 1], fill=0)
    _save_1bit(mask, dest)
    print(f"  {dest.name}  <- drawn letter tile '{letter}'")


def main() -> int:
    here = Path(__file__).resolve().parent
    out = here / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    parts = here / "icons" / "_parts"
    icon_fetch.fluent(PARTS, parts)
    composites(out, parts)
    spool(out)
    brim_ears(out)
    brand_marks.ensure(out / "bambustudio.png", "bambulab")
    letter_tile(out / "prusaslicer.png", "P")
    letter_tile(out / "orcaslicer.png", "O")
    letter_tile(out / "prusa_gcodeviewer.png", "G")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
