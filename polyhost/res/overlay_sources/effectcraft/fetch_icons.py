#!/usr/bin/env python3
"""Fetch + render the EffectCraft shortcut icons (reproducible source step).

EffectCraft (storytold/effectcraft, MIT OR Apache-2.0) is the ArtCraft suite's
After Effects-like motion graphics / VFX compositor. Its keymap is After
Effects' default layout, so wherever an action matches the reference
`aftereffects/` set the committed icon is COPIED from there (byte-identical, so
both apps draw the same cell and the icon library stores it once).

Everything else: Microsoft Fluent UI System Icons (MIT, house style), Material
Symbols (Apache-2.0, `ms:`) for Fluent's gaps, and a handful of drawn text
badges (resolution fractions, channel letters, fast-preview modes) where no
glyph set says "1/2" or "Red channel".

The ESC **program mark** is EffectCraft's OWN app icon (the engraved unicorn,
`assets/app-icon/effectcraft.ico`, MIT OR Apache-2.0 per that directory's
LICENSE.txt and .attribution files), 48 px frame, rendered with
`program_icon_mode: bright`, threshold 130 (see bindings.yaml for the sweep).
Guarded by `program_marks.own_icon`, so a re-run never clobbers it; the drawn
badges are guarded the same way.

    PYTHONPATH=. python polyhost/res/overlay_sources/effectcraft/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import icon_fetch  # noqa: E402
import program_marks  # noqa: E402

EC_ICO = ("https://raw.githubusercontent.com/storytold/effectcraft/"
          "549e9d825132986d6167c1432cd3328efcbb0278/assets/app-icon/effectcraft.ico")

# Same action as the After Effects reference set -> same committed bytes.
BORROW = {f"{n}.png": "aftereffects" for n in (
    "anchorpoint", "position", "scale", "rotation", "opacity", "feather",
    "effects", "keyframes", "select", "hand", "zoom", "pen", "shape",
    "panbehind", "gotoin", "gotoout", "preview", "newcomp", "open", "save",
    "import", "compsettings", "renderqueue", "solid", "type", "undo", "redo",
    "cut", "copy", "paste", "selectall", "duplicate", "splitlayer",
    "precompose",
)}

FLUENT = {
    # --- reveal / tools (no modifier) ---
    "masks": "Shape Subtract",
    "levels": "Speaker 2",
    "camera": "Camera",
    "orbit": "ms:3d_rotation",
    "pancamera": "ms:pan_tool_alt",
    "dolly": "ms:open_in_full",
    "scrolltime": "ms:my_location",
    "scrolllayer": "ms:vertical_align_top",
    "wa_begin": "ms:align_horizontal_left",
    "wa_end": "ms:align_horizontal_right",
    "prevkey": "Arrow Previous",
    "nextkey": "Arrow Next",
    "movein": "ms:line_start_arrow_notch",
    "moveout": "ms:line_end_arrow_notch",
    "trimin": "ms:keyboard_tab_rtl",
    "trimout": "ms:keyboard_tab",
    "zoomtime_in": "ms:unfold_more_double",
    "zoomtime_out": "ms:unfold_less_double",
    "zoomframe": "ms:zoom_in_map",
    "safemargins": "ms:fit_screen",
    "swappanel": "Arrow Swap",
    "maxpanel": "Maximize",
    "maxapp": "Full Screen Maximize",
    "actualsize": "Ratio One To One",
    "viewzoomin": "ms:zoom_in",
    "viewzoomout": "ms:zoom_out",
    "fit": "ms:fit_page",
    "fitto100": "ms:aspect_ratio",
    "help": "Question Circle",
    "deselectall": "Select All Off",
    "effectcontrols": "Options",
    "switches": "Toggle Left",
    "easyease": "ms:line_curve",
    "easyeasein": "ms:line_start_circle",
    "easyeaseout": "ms:line_end_circle",
    "view_front": "Cube",
    "view_custom": "Cube Rotate",
    "view_activecam": "Video",
    "miniflow": "Flowchart Circle",
    "flowchart": "Flowchart",
    "rename": "Rename",
    "clear": "Delete",
    "deletenoconfirm": "Delete Dismiss",
    "gostart": "Previous",
    "goend": "Next",
    "wa_gostart": "ms:first_page",
    "wa_goend": "ms:last_page",
    "prevframe": "Chevron Left",
    "nextframe": "Chevron Right",
    "back10": "Chevron Double Left",
    "fwd10": "Chevron Double Right",
    "nudge_up": "Arrow Up",
    "nudge_down": "Arrow Down",
    "nudge_left": "Arrow Left",
    "nudge_right": "Arrow Right",
    "nudge10_up": "ms:keyboard_double_arrow_up",
    "nudge10_down": "ms:keyboard_double_arrow_down",
    "nudge10_left": "ms:keyboard_double_arrow_left",
    "nudge10_right": "ms:keyboard_double_arrow_right",
    "nextcomp": "ms:switch_right",
    "prevcomp": "ms:switch_left",
    "nextpanel": "ms:tab_move",
    "prevpanel": "ms:tab_inactive",
    "blend_prev": "Arrow Circle Left",
    "blend_next": "Arrow Circle Right",
    "parentcol": "Link",
    "grapheditor": "ms:show_chart",
    "snapshot": "ms:photo_camera",
    "purgesnapshot": "ms:no_photography",
    "ws_default": "ms:dashboard",
    "ws_standard": "ms:space_dashboard",
    "ws_small": "ms:view_compact",
    # --- Alt ---
    "bilinear": "ms:blur_linear",
    "bicubic": "ms:blur_on",
    "rotobrush": "ms:auto_fix_normal",
    "masknext": "ms:move_down",
    "maskprev": "ms:move_up",
    "keynudge_l": "ms:line_start_diamond",
    "keynudge_r": "ms:line_end_diamond",
    "keynudge10_l": "ms:fast_rewind",
    "keynudge10_r": "ms:fast_forward",
    "layer_tostart": "ms:line_start_square",
    "layer_toend": "ms:line_end_square",
    "layer_earlier": "ms:arrow_left_alt",
    "layer_later": "ms:arrow_right_alt",
    "layer_earlier10": "ms:keyboard_return",
    "layer_later10": "ms:subdirectory_arrow_right",
    "expression": "Math Formula",
    "gototime": "Clock",
    "newviewer": "Window New",
    "shadows": "ms:shadow",
    # --- Cmd/Ctrl ---
    "editoriginal": "Open",
    "find": "Search",
    "group": "Group",
    "ungroup": "ms:ungroup",
    "replacefootage": "Arrow Sync",
    "lock": "Lock Closed",
    "unlock": "Lock Open",
    "puppet": "Pin",
    "quit": "Power",
    "rulers": "Ruler",
    "quality_best": "ms:high_quality",
    "brush": "Paint Brush",
    "p_project": "Folder",
    "p_tools": "Toolbox",
    "p_info": "Info",
    "p_preview": "Play Circle",
    "p_audio": "Music Note 2",
    "p_effects": "Sparkle",
    "p_character": "Text Font",
    "p_paragraph": "Text Paragraph",
    "p_paint": "Paint Bucket",
    "p_brushes": "ms:brush",
    "grid": "Grid",
    "guides": "ms:grid_guides",
    "addfootage": "Video Add",
    "twirl": "ms:unfold_more",
    "sendbackward": "ms:arrow_downward",
    "bringforward": "ms:arrow_upward",
    "sendtoback": "ms:flip_to_back",
    "bringtofront": "ms:flip_to_front",
    "centerview": "ms:center_focus_strong",
    "layer_prev": "ms:keyboard_arrow_up",
    "layer_next": "ms:keyboard_arrow_down",
    # --- Cmd+Shift ---
    "snapgrid": "ms:grid_on",
    "snapguides": "ms:border_inner",
    "stretchin": "ms:line_start",
    "stretchout": "ms:line_end",
    "extend_prev": "ms:expand_circle_up",
    "extend_next": "ms:expand_circle_down",
    "removeeffects": "ms:auto_fix_off",
    "layercontrols": "Eye",
    "maskinvert": "ms:invert_colors",
    "velocity": "Top Speed",
    "maskshape": "ms:pentagon",
    "newmask": "Shape Union",
    "saveas": "Save Edit",
    "quickapply": "Flash",
    "quality_draft": "ms:sd",
    "pastereversed": "ms:swap_horiz",
    "closeall": "Dismiss Square Multiple",
    "trimcomp": "Crop",
    "layersettings": "ms:tune",
    # --- Cmd+Alt ---
    "shortcuts": "Keyboard",
    "preferences": "Settings",
    "selectkeys": "ms:select_all",
    "wa_toselection": "ms:settings_ethernet",
    "copylinks": "Link Square",
    "fitcomp": "Resize Large",
    "interpret": "Filmstrip",
    "holdkey": "ms:pause",
    "importmulti": "Document Multiple",
    "interpolation": "ms:timeline",
    "reload": "Arrow Clockwise",
    "newproject": "Document Add",
    "autoorient": "Compass Northwest",
    "proxy": "ms:switch_video",
    "timereverse": "ms:u_turn_left",
    "saveframe": "ms:image",
    "timeremap": "ms:timer",
    "viewoptions": "Eye Tracking",
    "applyinterp": "ms:format_paint",
    "adjustment": "Layer Diagonal",
    "compfromsel": "Add Square Multiple",
    "rq_panel": "ms:list_alt",
    # --- Cmd+Alt+Shift ---
    "lockguides": "ms:lock_reset",
    "prev_inout": "ms:skip_previous",
    "next_inout": "ms:skip_next",
    "newcamera": "Camera Add",
    "lasteffect": "ms:auto_fix_high",
    "recentpreset": "ms:animation",
    "fitheight": "ms:height",
    "fitwidth": "ms:width",
    "projectsettings": "Document Settings",
    "light": "Lightbulb",
    "newfolder": "Folder Add",
    "openrecent": "ms:history",
    "orientation": "ms:explore",
    "incrementsave": "Save Multiple",
    "newtext": "ms:text_fields",
    "wireframe": "ms:deployed_code",
    "hideothervideo": "Eye Off",
    "nullobject": "ms:select",
    "lookat": "ms:center_focus_weak",
    "deselectkeys": "ms:deselect",
}

# Drawn text badges: (text, style). "plain" = bare text, "ring" = text in a
# circle outline, "disc" = text knocked out of a filled disc, "box" = text in
# a rounded-rect outline. Black on transparent, so the file's luma mode reads it.
BADGES = {
    "res_full": ("1/1", "plain"),
    "res_half": ("1/2", "plain"),
    "res_quarter": ("1/4", "plain"),
    "res_custom": ("1/n", "plain"),
    "ch_red": ("R", "ring"),
    "ch_green": ("G", "ring"),
    "ch_blue": ("B", "ring"),
    "ch_alpha": ("A", "ring"),
    "ch_red_col": ("R", "disc"),
    "ch_green_col": ("G", "disc"),
    "ch_blue_col": ("B", "disc"),
    "ch_rgbstraight": ("RGB", "box"),
    "fp_final": ("FQ", "box"),
    "fp_adaptive": ("AR", "box"),
    "fp_draft": ("DR", "box"),
    "fp_fastdraft": ("FD", "box"),
    "fp_wireframe": ("WF", "box"),
}

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
INK = (0, 0, 0, 255)
CLEAR = (0, 0, 0, 0)


def _badge(path: Path, text: str, style: str) -> None:
    """Draw one text badge at 4x and downscale to 96 px (black on transparent)."""
    ss, u = 4, 96 * 4
    im = Image.new("RGBA", (u, u), CLEAR)
    d = ImageDraw.Draw(im)
    w = int(u * 0.075)  # stroke
    box = [w, w + u // 8, u - w, u - w - u // 8]
    if style == "ring":
        d.ellipse([w, w, u - w, u - w], outline=INK, width=w)
    elif style == "disc":
        d.ellipse([0, 0, u - 1, u - 1], fill=INK)
    elif style == "box":
        d.rounded_rectangle(box, radius=u // 10, outline=INK, width=w)
    # widest font size that fits the inner area
    inner = (u * 0.62, u * 0.5) if style in ("ring", "disc") else (u * 0.80, u * 0.50)
    if style == "box":
        inner = (u * 0.72, u * 0.42)
    size = u
    while size > 8:
        f = ImageFont.truetype(BOLD, size)
        l, t, r, b = d.textbbox((0, 0), text, font=f)
        if r - l <= inner[0] and b - t <= inner[1]:
            break
        size -= 4
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    x = (u - (r - l)) / 2 - l
    y = (u - (b - t)) / 2 - t
    d.text((x, y), text, font=f, fill=CLEAR if style == "disc" else INK)
    im.resize((u // ss, u // ss), Image.LANCZOS).save(path)


def _key_toggle(path: Path) -> None:
    """Keyframe diamond with a plus inside: "add or remove keyframe"."""
    u = 96 * 4
    im = Image.new("RGBA", (u, u), CLEAR)
    d = ImageDraw.Draw(im)
    c, r, w = u // 2, int(u * 0.46), int(u * 0.075)
    d.polygon([(c, c - r), (c + r, c), (c, c + r), (c - r, c)], outline=INK, width=w)
    a = int(r * 0.42)
    d.rectangle([c - a, c - w // 2, c + a, c + w // 2], fill=INK)
    d.rectangle([c - w // 2, c - a, c + w // 2, c + a], fill=INK)
    im.resize((96, 96), Image.LANCZOS).save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.borrow(BORROW, out)
    n = icon_fetch.fluent(FLUENT, out)
    for stem, (text, style) in sorted(BADGES.items()):
        p = out / f"{stem}.png"
        if p.exists():
            print(f"  {p.name}  <- committed asset (left as-is)")
        else:
            _badge(p, text, style)
            print(f"  {p.name}  <- drawn badge {text!r} ({style})")
    if (out / "keytoggle.png").exists():
        print("  keytoggle.png  <- committed asset (left as-is)")
    else:
        _key_toggle(out / "keytoggle.png")
        print("  keytoggle.png  <- drawn (diamond + plus)")
    program_marks.own_icon(out / "effectcraft.png", EC_ICO, frame=48,
                           credit="storytold/effectcraft assets/app-icon/effectcraft.ico (MIT OR Apache-2.0)")
    print(f"Wrote {len(BORROW)} borrowed + {n} fetched + {len(BADGES) + 1} drawn icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
