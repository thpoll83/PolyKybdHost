#!/usr/bin/env python3
"""Fetch + render the Windows File Explorer shortcut icons (reproducible).

By default all glyphs are Microsoft Fluent UI System Icons (MIT) — the open twin
of Win11's Segoe Fluent, license-clean (host is GPL-3.0-or-later). For *pixel-exact*
Windows 11 glyphs, drop the proprietary `SegoeIcons.ttf`
(C:\\Windows\\Fonts\\SegoeIcons.ttf) into this folder (it is git-ignored, not
redistributed) and re-run: every action Segoe documents a codepoint for is then
rendered from the real font, and the rest (the Win-key shell shortcuts, which
SEGOE has no map for) still come from Fluent.

    pip install cairosvg
    python polyhost/res/overlay_sources/explorer/fetch_icons.py
"""
from __future__ import annotations

import time
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

    # --- Win-key (GUI) combos, protocol 12 ----------------------------------
    # These are Windows *shell* shortcuts, not Explorer commands, but they are
    # exactly the ones a user reaches for while a file window has focus, and
    # they are what populates the combo/extra/gui overlay tiers.
    "winexplorer": "Folder Open/SVG/ic_fluent_folder_open_24_regular.svg",
    "showdesktop": "Desktop/SVG/ic_fluent_desktop_24_regular.svg",
    "lock": "Lock Closed/SVG/ic_fluent_lock_closed_24_regular.svg",
    "run": "Window Dev Tools/SVG/ic_fluent_window_dev_tools_24_regular.svg",
    "settings": "Settings/SVG/ic_fluent_settings_24_regular.svg",
    "clipboard": "Clipboard/SVG/ic_fluent_clipboard_24_regular.svg",
    "quicklink": "Apps List/SVG/ic_fluent_apps_list_24_regular.svg",
    "taskview": "Window Multiple/SVG/ic_fluent_window_multiple_24_regular.svg",
    "project": "Projection Screen/SVG/ic_fluent_projection_screen_24_regular.svg",
    "snip": "Screenshot/SVG/ic_fluent_screenshot_24_regular.svg",
    "moveleft": "Panel Left/SVG/ic_fluent_panel_left_24_regular.svg",
    "moveright": "Panel Right/SVG/ic_fluent_panel_right_24_regular.svg",
    "restorewin": "Arrow Maximize/SVG/ic_fluent_arrow_maximize_24_regular.svg",
    "record": "Record/SVG/ic_fluent_record_24_regular.svg",
    "gamecapture": "Camera/SVG/ic_fluent_camera_24_regular.svg",
    "desktopnew": "Tab Add/SVG/ic_fluent_tab_add_24_regular.svg",
    "desktopprev": "Chevron Left/SVG/ic_fluent_chevron_left_24_regular.svg",
    "desktopnext": "Chevron Right/SVG/ic_fluent_chevron_right_24_regular.svg",
    "gfxreset": "Desktop Sync/SVG/ic_fluent_desktop_sync_24_regular.svg",
}


def _get(url: str, attempts: int = 5) -> bytes:
    """Fetch with backoff — raw.githubusercontent drops connections under the
    session's egress proxy often enough that a single-shot fetch fails a whole
    run partway through, leaving a half-written icons/ dir."""
    for i in range(attempts):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "polykybd"}),
                timeout=30).read()
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(2 ** i)
    raise AssertionError("unreachable")


def _render_segoe(out: Path, ttf: Path) -> set:
    """Render every action Segoe HAS a documented codepoint for, from the real font.

    Black glyph centred on white (so the generator's `mode: luma` lights it).
    The committed program icon (explorer.png) is left alone if present.
    Returns the set of action names written, so the caller can fill the rest from
    Fluent — SEGOE covers the Explorer commands but not the Win-key shell
    shortcuts, and a partial Segoe run must not leave those icons missing.
    """
    font = ImageFont.truetype(str(ttf), int(RENDER_PX * 0.82))
    done = set()
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
        done.add(action)
    return done


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)

    # Don't clobber a committed hand-made program icon if one was dropped in.
    skip = {"explorer"} if (out / "explorer.png").exists() else set()

    ttf = Path(__file__).resolve().parent / SEGOE_TTF
    if ttf.exists():
        print(f"Using genuine Segoe Fluent Icons font: {ttf.name}")
        skip |= _render_segoe(out, ttf)
    for fname, asset in MS_ICONS.items():
        if fname in skip:
            continue
        enc = "/".join(urllib.parse.quote(s) for s in asset.split("/"))
        png = cairosvg.svg2png(bytestring=_get(MS.format(enc)),
                               output_width=RENDER_PX, output_height=RENDER_PX)
        (out / f"{fname}.png").write_bytes(png)
        print(f"  {fname}.png  <- ms-fluent/{asset.split('/')[0]}")
    print(f"Wrote {len(set(MS_ICONS) - skip)} Fluent icons to {out} "
          f"(drop {SEGOE_TTF} here for genuine Win11 glyphs on the Explorer commands)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
