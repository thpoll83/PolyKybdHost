#!/usr/bin/env python3
"""Fetch + render the FreeCAD shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. The standard view names
and the Sketcher constraint symbols are text in DejaVu Sans Bold; the tangent
symbol is drawn. `BADGED` draws a glyph over a short word, for a key that
does a different thing than another key with the same glyph (TechDraw's
dimensions, the Assembly joints, BIM's panel and nudge keys). The ESC mark
is the FreeCAD logo (Simple Icons, CC0-1.0, via brand_marks), and on each
workbench set the logo with the workbench name (`esc_<set>.png`), as the Godot
set does.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/freecad/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand_marks  # noqa: E402
import dcc_glyphs  # noqa: E402
import icon_fetch  # noqa: E402

RENDER_PX = 96
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
WORD_FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

FLUENT = {
    # --- file, edit, tools ---
    "import": "ms:input",
    "export": "ms:file_export",
    "refresh": "ms:refresh",
    "recompute": "ms:sync",
    "properties": "ms:tune",
    "console": "ms:terminal",
    "runmacro": "ms:play_circle",
    "whatsthis": "ms:help_center",
    "help": "ms:help",
    "appearance": "ms:format_paint",
    "preferences": "Settings",
    "rename": "ms:drive_file_rename_outline",
    # --- view ---
    "freeze": "ms:ac_unit",
    "visibility": "Eye",
    "home": "ms:home",
    "isometric": "ms:view_in_ar",
    "rotleft": "ms:rotate_left",
    "rotright": "ms:rotate_right",
    "fullscreen": "ms:fullscreen",
    "boxzoom": "ms:zoom_in_map",
    "boxsel": "ms:select",
    "boxelemsel": "ms:select_all",
    "panelleft": "ms:left_panel_open",
    "panelright": "ms:right_panel_open",
    "paneltop": "ms:top_panel_open",
    "panelbottom": "ms:bottom_panel_open",
    "storeview": "ms:bookmark_add",
    "recallview": "ms:bookmark",
    "nextwin": "ms:select_window",
    "prevwin": "ms:select_window_2",
    # --- workbenches ---
    "dimension": "ms:straighten",
    "pointonobj": "ms:commit",
    "coincident": "ms:adjust",
    "horizontal": "ms:horizontal_rule",
    "transform": "ms:open_with",
    "snaplock": "ms:lock",
    "wireframe": "ms:grid_on",
    # --- BIM (the per-workbench set) ---
    "trash": "ms:delete",
    "viewsmanager": "ms:view_list",
    "wpview": "ms:crop_free",
    "nudgeswitch": "ms:swap_horiz",
    "nudgeextend": "ms:open_in_full",
    "nudgeshrink": "ms:close_fullscreen",
    "nudgerotright": "ms:rotate_90_degrees_cw",
    # --- Assembly ---
    "insertcomp": "ms:add_box",
    "fixedjoint": "ms:anchor",
    "revolute": "ms:autorenew",
    "slider": "ms:swap_vert",
    "balljoint": "ms:radio_button_checked",
    "gears": "ms:settings",
    "screwjoint": "ms:hardware",
    "beltjoint": "ms:sync_alt",
    "bom": "ms:list_alt",
    "newassembly": "ms:deployed_code",
    "solve": "ms:task_alt",
    "newpart": "ms:note_add",
    "exploded": "ms:unfold_more",
    "simulation": "ms:animation",
    # --- Spreadsheet ---
    "bold": "ms:format_bold",
    "italic": "ms:format_italic",
    "underline": "ms:format_underlined",
    "alias": "ms:label",
}

TEXT = {
    # standard views (keys 0..6)
    "front": "FRT",
    "top": "TOP",
    "right": "RGT",
    "rear": "REAR",
    "bottom": "BTM",
    "left": "LFT",
    # Sketcher constraints
    "horver": "H/V",
    "vertical": "|",
    "hdim": "↔",
    "vdim": "↕",
    "parallel": "∥",
    "perpendicular": "⊥",
    "raddia": "⌀",
    "equal": "=",
    "symmetric": "⋈",
    # Assembly joints Material Symbols has no glyph for
    "cylindrical": "CYL",
    "angle": "∠",
    "rackpinion": "R+P",
    "gearbelt": "G/B",
}

# A glyph (an icon written above) over a word: a key whose action differs from
# another key with the same glyph. TD = TechDraw, JNT = Assembly joint,
# WP = working plane.
BADGED = {
    "fullscreen_win": ("fullscreen", "WIN"),
    "panelbottom_all": ("panelbottom", "ALL"),
    "dimension_td": ("dimension", "TD"),
    "hdim_td": ("hdim", "TD"),
    "vdim_td": ("vdim", "TD"),
    "dimension_jnt": ("dimension", "JNT"),
    "parallel_jnt": ("parallel", "JNT"),
    "perpendicular_jnt": ("perpendicular", "JNT"),
    # crop_free alone looks like F11's full-screen corners
    "wpview_wp": ("wpview", "WP"),
}
GLYPH_H = 0.64   # share of the height the glyph takes; the word gets the rest
WORD_PX = 30     # DejaVu Sans Bold size at RENDER_PX


def _draw_badged(path: Path, glyph: Path, word: str) -> None:
    """``glyph`` fitted into the upper part, ``word`` centred below it, black
    on transparent like the fetched glyphs."""
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    g = Image.open(glyph).convert("RGBA")
    g = g.crop(g.getbbox())
    top = int(RENDER_PX * GLYPH_H)
    scale = min(RENDER_PX / g.width, top / g.height)
    g = g.resize((max(1, round(g.width * scale)), max(1, round(g.height * scale))), Image.LANCZOS)
    img.alpha_composite(g, ((RENDER_PX - g.width) // 2, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, WORD_PX)
    box = d.textbbox((0, 0), word, font=font)
    if box[2] - box[0] > RENDER_PX:
        raise ValueError(f"{path.name}: word {word!r} is too wide")
    x = (RENDER_PX - (box[2] - box[0])) / 2 - box[0]
    d.text((x, RENDER_PX - 1 - box[3]), word, font=font, fill=(0, 0, 0, 255))
    img.save(path)


def _draw_text(path: Path, text: str) -> None:
    """Black text on transparent, like the fetched glyphs, scaled so its ink
    fills the icon."""
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    probe = ImageFont.truetype(FONT, 100)
    box = d.textbbox((0, 0), text, font=probe)
    scale = min(RENDER_PX * 0.95 / (box[2] - box[0]), RENDER_PX * 0.9 / (box[3] - box[1]))
    font = ImageFont.truetype(FONT, max(8, int(100 * scale)))
    box = d.textbbox((0, 0), text, font=font)
    x = (RENDER_PX - (box[2] - box[0])) / 2 - box[0]
    y = (RENDER_PX - (box[3] - box[1])) / 2 - box[1]
    d.text((x, y), text, font=font, fill=(0, 0, 0, 255))
    img.save(path)


def _draw_tangent(path: Path) -> None:
    """A circle with a line touching its top, the usual tangent symbol."""
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((22, 30, 74, 82), outline=(0, 0, 0, 255), width=8)
    d.rectangle((2, 22, RENDER_PX - 3, 30), fill=(0, 0, 0, 255))
    img.save(path)


# ESC marks: the logo alone on the fallback and global sets, the logo with the
# workbench name on each workbench set (gen_workbench_bindings.py names them).
ESC_WORDS = {"sketcher": "SKETCH", "assembly": "ASM", "bim": "BIM", "draft": "DRAFT",
             "techdraw": "TECH", "spreadsheet": "SHEET"}
ESC_W, ESC_H, ESC_LOGO = 72, 40, 34
ESC_WORD_PX, ESC_WORD_W = 22, 34


def esc_mark(dest: Path, word: str, logo_png: Path) -> None:
    """`word` (Liberation Sans Bold, at most ESC_WORD_W px wide) left of the
    logo (its alpha, ESC_LOGO px), both 1 bit (as in the Godot set)."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    logo = Image.open(logo_png).convert("RGBA").split()[3].resize((ESC_LOGO, ESC_LOGO), Image.LANCZOS)
    mask = Image.new("L", (ESC_W, ESC_H), 0)
    mask.paste(logo.point(lambda v: 255 if v >= 128 else 0),
               (ESC_W - ESC_LOGO, (ESC_H - ESC_LOGO) // 2))
    px = ESC_WORD_PX
    while px > 8:
        l, t, r, b = ImageFont.truetype(WORD_FONT, px).getbbox(word)
        if r - l <= ESC_WORD_W:
            break
        px -= 1
    layer = Image.new("L", (r - l + 2, b - t + 2), 0)
    ImageDraw.Draw(layer).text((1 - l, 1 - t), word, fill=255, font=ImageFont.truetype(WORD_FONT, px))
    layer = layer.point(lambda v: 255 if v > 127 else 0)
    layer = layer.crop(layer.getbbox())
    mask.paste(255, (0, (ESC_H - layer.height) // 2), layer)
    img = Image.new("RGBA", (ESC_W, ESC_H), (255, 255, 255, 0))
    img.putalpha(mask)
    img.save(dest)
    print(f"  {dest.name}  <- drawn: '{word}' + freecad.png")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    for name, text in TEXT.items():
        _draw_text(out / f"{name}.png", text)
        n += 1
    _draw_tangent(out / "tangent.png")
    n += 1
    for name, (glyph, word) in BADGED.items():
        dcc_glyphs.guarded(out / f"{name}.png",
                           lambda p, g=glyph, w=word: _draw_badged(p, out / f"{g}.png", w),
                           f"{glyph}.png over '{word}'")
        n += 1
    brand_marks.ensure(out / "freecad.png", "freecad")
    for name, word in ESC_WORDS.items():
        esc_mark(out / f"esc_{name}.png", word, out / "freecad.png")
    print(f"Wrote {n} icons to {out} ({len(TEXT)} drawn as text)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
