#!/usr/bin/env python3
"""Fetch + render the Godot editor shortcut icons (reproducible).

Glyphs: Material Symbols (Apache-2.0) through `ms:` and one Microsoft Fluent
UI System Icon (MIT). Some icons are copied byte-identical from the Blender and
VS Code sets (`icon_fetch.borrow`). A few keys are text (DejaVu Sans Bold) or
a glyph with a small arrow drawn here. The ESC mark is the Godot logo from
Simple Icons (`godotengine`, artwork CC0; the logo is by Andrea Calabró,
CC BY 4.0), and each per-screen set adds the screen's name beside it. See
SOURCES.md.

    pip install cairosvg Pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/godot/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand_marks  # noqa: E402
import icon_fetch  # noqa: E402

RENDER_PX = 96
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
WORD_FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

FLUENT = {
    # --- main screens ---
    "screen_script": "ms:code",
    "screen_game": "ms:sports_esports",
    "screen_assets": "ms:storefront",
    # --- files ---
    "newscene": "ms:note_add",
    "inherited": "ms:schema",
    "saveall": "Save Multiple",
    "closescene": "ms:tab_close",
    "reopen": "ms:restore_page",
    "projectlist": "ms:list_alt",
    "openscene": "ms:movie",
    "openscript": "ms:description",
    "filterfiles": "ms:filter_alt",
    "help": "ms:help",
    # --- run ---
    "play": "ms:play_arrow",
    "playscene": "ms:play_circle",
    "playcustom": "ms:slideshow",
    "stop": "ms:stop",
    "continue": "ms:resume",
    "suspend": "ms:pause_circle",
    "nextframe": "ms:skip_next",
    # --- window and panels ---
    "distraction": "ms:self_improvement",
    "fullscreen": "ms:fullscreen",
    "screenshot": "ms:screenshot_monitor",
    "expandpanel": "ms:open_in_full",
    "bottompanel": "ms:bottom_panel_open",
    "debugger": "ms:bug_report",
    "filesystem": "ms:folder",
    "animation": "ms:animation",
    "audio": "ms:graphic_eq",
    "shader": "ms:gradient",
    # --- scene tree ---
    "addnode": "ms:add_circle",
    "instantiate": "ms:link",
    "pastesibling": "ms:content_paste_go",
    "pastereplace": "ms:swap_horiz",
    "nodepath": "ms:route",
    "moveup": "ms:move_up",
    "movedown": "ms:move_down",
    "forcedelete": "ms:delete_forever",
    # --- 2D / 3D tools ---
    "select": "ms:arrow_selector_tool",
    "transform": "ms:transform",
    "scenepaint": "ms:brush",
    "pan": "ms:pan_tool",
    "ruler": "ms:straighten",
    "localspace": "ms:explore",
    "smartsnap": "ms:join",
    "gridsnap": "ms:grid_guides",
    "grid": "ms:grid_on",
    "helpers": "ms:architecture",
    "guides": "ms:border_inner",
    "center": "ms:center_focus_weak",
    "resetpos": "ms:pin_drop",
    "resetrot": "ms:rotate_left",
    "resetscale": "ms:photo_size_select_large",
    "lock": "ms:lock",
    "unlock": "ms:lock_open",
    "visibility": "ms:visibility",
    "keyexisting": "ms:key_vertical",
    "clearpose": "ms:person_off",
    "bones": "ms:skeleton",
    "trackball": "ms:3d_rotation",
    "preserve": "ms:account_tree",
    "vertexsnap": "ms:polyline",
    "freelook": "ms:flight",
    "camerapreview": "ms:videocam",
    "vp1": "ms:crop_square",
    "vp2": "ms:splitscreen",
    "vp2alt": "ms:vertical_split",
    "vp3": "ms:view_quilt",
    "vp3alt": "ms:view_compact",
    "vp4": "ms:grid_view",
    "fovless": "ms:photo_size_select_small",
    "fovmore": "ms:panorama_wide_angle",
    "fovreset": "ms:restart_alt",
    "floor": "ms:vertical_align_bottom",
    "collision": "ms:move_down",
    "alignrot": "ms:screen_rotation_alt",
    "aligntransform": "ms:filter_center_focus",
    # --- script editor ---
    "nextoccurrence": "ms:select",
    "complete": "ms:magic_button",
    "lineup": "ms:arrow_upward",
    "linedown": "ms:arrow_downward",
    "deleteline": "ms:format_strikethrough",
    "joinlines": "ms:call_merge",
    "fold": "ms:unfold_less",
    "region": "ms:data_object",
    "dupselection": "ms:control_point_duplicate",
    "duplines": "ms:stacks",
    "evaluate": "ms:calculate",
    "wordwrap": "ms:wrap_text",
    "trim": "ms:format_clear",
    "tospaces": "ms:space_bar",
    "totabs": "ms:keyboard_tab",
    "autoindent": "ms:format_indent_increase",
    "replace": "ms:find_replace",
    "contexthelp": "ms:contact_support",
    "bookmark": "ms:bookmark_add",
    "clearbreakpoints": "ms:playlist_remove",
    "newscript": "ms:post_add",
    "newtextfile": "ms:text_snippet",
    "savescript": "ms:save",
    "softreload": "ms:refresh",
    "runscript": "ms:terminal",
}

# Same action as in a sibling set: copied byte-identical.
BORROW = {
    "move.png": "blender",
    "rotate.png": "blender",
    "scale.png": "blender",
    "snap.png": "blender",
    "origin.png": "blender",
    "fit_view.png": "blender",
    "key_insert.png": "blender",
    "duplicate.png": "blender",
    "rename.png": "blender",
    "batch_rename.png": "blender",
    "group.png": "blender",
    "ungroup.png": "blender",
    "tab_next.png": "blender",
    "tab_prev.png": "blender",
    "breakpoint.png": "vscode",
    "comment.png": "vscode",
    "closeeditor.png": "vscode",
    "findinfiles.png": "vscode",
    "replaceinfiles.png": "vscode",
    "goback.png": "vscode",
    "goforward.png": "vscode",
    "gotoline.png": "vscode",
    "gotosymbol.png": "vscode",
    "output.png": "vscode",
    "palette.png": "vscode",
    "pause.png": "vscode",
    "quickopen.png": "vscode",
    "settings.png": "vscode",
    "sidebar.png": "vscode",
    "stepinto.png": "vscode",
    "stepover.png": "vscode",
}

TEXT = {
    "screen_2d": "2D",
    "screen_3d": "3D",
    "zoom100": "1:1",
    "upper": "AB",
    "lower": "ab",
    "capitalize": "Ab",
}

# A glyph with a small triangle beside it, for the next/previous pairs.
# name -> (source glyph, Material name if not a fetched file, direction)
ARROWED = {
    "findnext": ("ms:search", "down"),
    "findprev": ("ms:search", "up"),
    "bookmarknext": ("ms:bookmark", "down"),
    "bookmarkprev": ("ms:bookmark", "up"),
    "nextbreakpoint": ("ms:radio_button_checked", "down"),
    "prevbreakpoint": ("ms:radio_button_checked", "up"),
}

# The ESC mark of each per-screen set: the screen's name left of the logo,
# over the whole 72x40 cell, drawn without the ESC legend
# (program_icon_legend: false). godot.yaml uses the plain logo.
ESC_WORDS = {"2d": "2D", "3d": "3D", "script": "CODE", "game": "GAME"}
ESC_W, ESC_H, ESC_LOGO = 72, 40, 34
ESC_WORD_PX, ESC_WORD_W = 22, 34


def _font(path: str, px: int):
    return ImageFont.truetype(path, px)


def _draw_text(path: Path, text: str) -> None:
    """Black text on transparent, like the fetched glyphs, scaled so its ink
    fills the icon (as in the QGIS set)."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    probe = _font(FONT, 100)
    box = d.textbbox((0, 0), text, font=probe)
    scale = min(RENDER_PX * 0.95 / (box[2] - box[0]), RENDER_PX * 0.9 / (box[3] - box[1]))
    font = _font(FONT, max(8, int(100 * scale)))
    box = d.textbbox((0, 0), text, font=font)
    x = (RENDER_PX - (box[2] - box[0])) / 2 - box[0]
    y = (RENDER_PX - (box[3] - box[1])) / 2 - box[1]
    d.text((x, y), text, font=font, fill=(0, 0, 0, 255))
    img.save(path)
    print(f"  {path.name}  <- drawn: {text!r}")


def _arrowed(path: Path, glyph: Path, direction: str) -> None:
    """`glyph` in the left 70 % of the icon and a filled triangle on the
    right, pointing down (next) or up (previous)."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    src = Image.open(glyph).convert("RGBA")
    w = int(RENDER_PX * 0.7)
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    img.paste(src.resize((w, w), Image.LANCZOS), (0, (RENDER_PX - w) // 2))
    d = ImageDraw.Draw(img)
    x0, x1 = w + 2, RENDER_PX - 2
    mid = RENDER_PX // 2
    h = (x1 - x0) // 2 + 4
    if direction == "down":
        pts = [(x0, mid - h // 2), (x1, mid - h // 2), ((x0 + x1) // 2, mid + h // 2)]
    else:
        pts = [(x0, mid + h // 2), (x1, mid + h // 2), ((x0 + x1) // 2, mid - h // 2)]
    d.polygon(pts, fill=(0, 0, 0, 255))
    img.save(path)
    print(f"  {path.name}  <- drawn: {glyph.name} + {direction} arrow")


def esc_mark(dest: Path, word: str, logo_png: Path) -> None:
    """`word` (Liberation Sans Bold, at most ESC_WORD_W px wide) left of the
    logo (its alpha, ESC_LOGO px), both 1 bit (as in the Emacs set)."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    logo = Image.open(logo_png).convert("RGBA").split()[3].resize((ESC_LOGO, ESC_LOGO), Image.LANCZOS)
    mask = Image.new("L", (ESC_W, ESC_H), 0)
    mask.paste(logo.point(lambda v: 255 if v >= 128 else 0),
               (ESC_W - ESC_LOGO, (ESC_H - ESC_LOGO) // 2))
    px = ESC_WORD_PX
    while px > 8:
        l, t, r, b = _font(WORD_FONT, px).getbbox(word)
        if r - l <= ESC_WORD_W:
            break
        px -= 1
    layer = Image.new("L", (r - l + 2, b - t + 2), 0)
    ImageDraw.Draw(layer).text((1 - l, 1 - t), word, fill=255, font=_font(WORD_FONT, px))
    layer = layer.point(lambda v: 255 if v > 127 else 0)
    layer = layer.crop(layer.getbbox())
    mask.paste(255, (0, (ESC_H - layer.height) // 2), layer)
    img = Image.new("RGBA", (ESC_W, ESC_H), (255, 255, 255, 0))
    img.putalpha(mask)
    img.save(dest)
    print(f"  {dest.name}  <- drawn: '{word}' + godot.png")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    icon_fetch.borrow(BORROW, out)
    for stem, text in TEXT.items():
        _draw_text(out / f"{stem}.png", text)
    # The plain glyphs of the arrowed icons are fetched to a scratch name and
    # removed again: only the composed icon is committed.
    for stem, (spec, direction) in ARROWED.items():
        dest = out / f"{stem}.png"
        if dest.exists():
            print(f"  {dest.name}  <- committed asset (left as-is)")
            continue
        tmp = f"_glyph_{stem}"
        icon_fetch.fluent({tmp: spec}, out)
        _arrowed(dest, out / f"{tmp}.png", direction)
        (out / f"{tmp}.png").unlink()
    brand_marks.ensure(out / "godot.png", "godotengine")
    for name, word in ESC_WORDS.items():
        esc_mark(out / f"esc_{name}.png", word, out / "godot.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
