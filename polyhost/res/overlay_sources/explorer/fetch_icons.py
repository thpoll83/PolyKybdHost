#!/usr/bin/env python3
"""Fetch + render the Windows File Explorer shortcut icons (reproducible).

By default all glyphs are Microsoft Fluent UI System Icons (MIT) — the open twin
of Win11's Segoe Fluent, license-clean (host is GPL-2.0). For *pixel-exact*
Windows 11 glyphs, drop the proprietary `SegoeIcons.ttf`
(C:\\Windows\\Fonts\\SegoeIcons.ttf) into this folder (it is git-ignored, not
redistributed) and re-run: the script then renders every action from the real
font at its documented codepoint, overriding the Fluent SVGs.

    pip install cairosvg
    python polyhost/res/overlay_sources/explorer/fetch_icons.py
"""
from __future__ import annotations

import urllib.parse
import urllib.request
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont

RENDER_PX = 96
MS = "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/assets/{}"

# Genuine Win11: action -> Segoe Fluent Icons codepoint (Microsoft's documented
# glyph map; resolved via Masterain98/Segoe-Fluent-Icons-List). Used only when
# SegoeIcons.ttf is present next to this file.
SEGOE_TTF = "SegoeIcons.ttf"
SEGOE = {
    "copy": 0xE8C8, "cut": 0xE8C6, "paste": 0xE77F, "undo": 0xE7A7, "redo": 0xE7A6,
    "selectall": 0xE8B3, "find": 0xE721, "newwindow": 0xE78B, "close": 0xE8BB,
    "address": 0xE71B, "rename": 0xE8AC, "delete": 0xE74D, "deleteperm": 0xE74D,
    "refresh": 0xE72C, "back": 0xE72B, "forward": 0xE72A, "uplevel": 0xE74A,
    "fullscreen": 0xE740, "properties": 0xE713, "newfolder": 0xE8F4,
    "explorer": 0xEC51,   # FileExplorerApp — the literal Win11 Explorer glyph
}

# action filename -> Microsoft Fluent System Icon (all MIT)
MS_ICONS = {
    "copy": "Copy/SVG/ic_fluent_copy_24_regular.svg",
    "cut": "Cut/SVG/ic_fluent_cut_24_regular.svg",
    "paste": "Clipboard Paste/SVG/ic_fluent_clipboard_paste_24_regular.svg",
    "undo": "Arrow Undo/SVG/ic_fluent_arrow_undo_24_regular.svg",
    "redo": "Arrow Redo/SVG/ic_fluent_arrow_redo_24_regular.svg",
    "selectall": "Select All On/SVG/ic_fluent_select_all_on_24_regular.svg",
    "find": "Search/SVG/ic_fluent_search_24_regular.svg",
    "newwindow": "Window New/SVG/ic_fluent_window_new_24_regular.svg",
    "close": "Dismiss/SVG/ic_fluent_dismiss_24_regular.svg",
    "address": "Location/SVG/ic_fluent_location_24_regular.svg",
    "rename": "Rename/SVG/ic_fluent_rename_24_regular.svg",
    "delete": "Delete/SVG/ic_fluent_delete_24_regular.svg",
    "deleteperm": "Delete Dismiss/SVG/ic_fluent_delete_dismiss_24_regular.svg",
    "refresh": "Arrow Sync/SVG/ic_fluent_arrow_sync_24_regular.svg",
    "back": "Arrow Left/SVG/ic_fluent_arrow_left_24_regular.svg",
    "forward": "Arrow Right/SVG/ic_fluent_arrow_right_24_regular.svg",
    "uplevel": "Arrow Up/SVG/ic_fluent_arrow_up_24_regular.svg",
    "fullscreen": "Full Screen Maximize/SVG/ic_fluent_full_screen_maximize_24_regular.svg",
    "properties": "Settings/SVG/ic_fluent_settings_24_regular.svg",
    "newfolder": "Folder Add/SVG/ic_fluent_folder_add_24_regular.svg",
    # program icon (ESC marker) — a plain folder; swap for the real Explorer logo
    # by committing icons/explorer.png (it will then be left as-is).
    "explorer": "Folder/SVG/ic_fluent_folder_24_regular.svg",
}


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "polykybd"}), timeout=30).read()


def _render_segoe(out: Path, ttf: Path) -> int:
    """Render every action's glyph from the real Segoe Fluent Icons font.

    Black glyph centred on white (so the generator's `mode: luma` lights it).
    The committed program icon (explorer.png) is left alone if present.
    """
    font = ImageFont.truetype(str(ttf), int(RENDER_PX * 0.82))
    n = 0
    for action, cp in SEGOE.items():
        if action == "explorer" and (out / "explorer.png").exists():
            print("  explorer.png  <- committed asset (left as-is)")
            continue
        img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (255, 255, 255, 255))
        d = ImageDraw.Draw(img)
        ch = chr(cp)
        bb = d.textbbox((0, 0), ch, font=font)
        d.text(((RENDER_PX - (bb[2] - bb[0])) / 2 - bb[0],
                (RENDER_PX - (bb[3] - bb[1])) / 2 - bb[1]), ch, font=font, fill=(0, 0, 0, 255))
        img.save(out / f"{action}.png")
        print(f"  {action}.png  <- segoe U+{cp:04X}")
        n += 1
    return n


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)

    ttf = Path(__file__).resolve().parent / SEGOE_TTF
    if ttf.exists():
        print(f"Using genuine Segoe Fluent Icons font: {ttf.name}")
        n = _render_segoe(out, ttf)
        print(f"Wrote {n} icons (Segoe) to {out}")
        return 0

    # Don't clobber a committed hand-made program icon if one was dropped in.
    skip = {"explorer"} if (out / "explorer.png").exists() else set()
    for fname, asset in MS_ICONS.items():
        if fname in skip:
            print(f"  {fname}.png  <- committed asset (left as-is)")
            continue
        enc = "/".join(urllib.parse.quote(s) for s in asset.split("/"))
        png = cairosvg.svg2png(bytestring=_get(MS.format(enc)),
                               output_width=RENDER_PX, output_height=RENDER_PX)
        (out / f"{fname}.png").write_bytes(png)
        print(f"  {fname}.png  <- ms-fluent/{asset.split('/')[0]}")
    print(f"Wrote {len(MS_ICONS) - len(skip)} icons to {out} "
          f"(drop {SEGOE_TTF} here for genuine Win11 glyphs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
