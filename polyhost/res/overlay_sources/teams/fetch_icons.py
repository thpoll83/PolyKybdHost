#!/usr/bin/env python3
"""Fetch + render the Microsoft Teams shortcut icons (reproducible).

All glyphs are Microsoft Fluent UI System Icons (MIT) — the native style for a
Microsoft app and license-clean (host is GPL-2.0). Rendered to 96x96 RGBA PNG;
the generator's `luma` mode keeps the linework at 1-bit. The program icon (ESC)
is a generic drawn chat-bubble mark with a "T" (no Microsoft Teams logo) — drop a
real Teams logo as icons/teams_logo.png to override (committed assets untouched).

    pip install cairosvg
    python polyhost/res/overlay_sources/teams/fetch_icons.py
"""
from __future__ import annotations

import urllib.parse
import urllib.request
from pathlib import Path

import cairosvg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RENDER_PX = 96
MS = "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/assets/{}"

# All probed against raw.githubusercontent.com (no 404) on 2026-06-15.
MS_ICONS = {
    # --- general (Ctrl) ---
    "search": "Search/SVG/ic_fluent_search_24_regular.svg",
    "newchat": "Chat Add/SVG/ic_fluent_chat_add_24_regular.svg",
    "settings": "Settings/SVG/ic_fluent_settings_24_regular.svg",
    "commands": "Slash Forward/SVG/ic_fluent_slash_forward_24_regular.svg",
    "shortcuts": "Keyboard/SVG/ic_fluent_keyboard_24_regular.svg",
    "zoomin": "Zoom In/SVG/ic_fluent_zoom_in_24_regular.svg",
    "zoomout": "Zoom Out/SVG/ic_fluent_zoom_out_24_regular.svg",
    "resetzoom": "Full Screen Maximize/SVG/ic_fluent_full_screen_maximize_24_regular.svg",
    "attach": "Attach/SVG/ic_fluent_attach_24_regular.svg",
    # --- app-bar navigation (Ctrl 1..6, default order) ---
    "activity": "Alert/SVG/ic_fluent_alert_24_regular.svg",
    "chat": "Chat/SVG/ic_fluent_chat_24_regular.svg",
    "teams": "People Team/SVG/ic_fluent_people_team_24_regular.svg",
    "calendar": "Calendar LTR/SVG/ic_fluent_calendar_ltr_24_regular.svg",
    "calls": "Call/SVG/ic_fluent_call_24_regular.svg",
    "files": "Document/SVG/ic_fluent_document_24_regular.svg",
    # --- call/meeting controls (Ctrl+Shift -> combo) ---
    "mute": "Mic Off/SVG/ic_fluent_mic_off_24_regular.svg",
    "camera": "Video/SVG/ic_fluent_video_24_regular.svg",
    "sharescreen": "Share Screen Start/SVG/ic_fluent_share_screen_start_24_regular.svg",
    "acceptvideo": "Video Person/SVG/ic_fluent_video_person_24_regular.svg",
    "acceptaudio": "Call/SVG/ic_fluent_call_24_regular.svg",
    "decline": "Call End/SVG/ic_fluent_call_end_24_regular.svg",
    "startaudio": "Call Add/SVG/ic_fluent_call_add_24_regular.svg",
    "startvideo": "Video Add/SVG/ic_fluent_video_add_24_regular.svg",
    "raisehand": "Hand Right/SVG/ic_fluent_hand_right_24_regular.svg",
    "background": "Blur/SVG/ic_fluent_blur_24_regular.svg",
    "expand": "Arrow Expand/SVG/ic_fluent_arrow_expand_24_regular.svg",
}


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "polykybd"}), timeout=30).read()


def _draw_teams_logo(path: Path) -> None:
    """Generic, license-clean Teams program mark (no Microsoft logo): a rounded-
    square *outline* with the monogram 'Te' drawn inside — the unified outlined-
    monogram style shared with the other app marks. White on transparent
    (alpha = the lit linework) -> program_icon_mode: alpha."""
    ss = 4
    u = RENDER_PX * ss
    m = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0.12 * u, 0.12 * u, 0.88 * u, 0.88 * u],
                        radius=0.16 * u, outline=255, width=int(u * 0.05))
    font = None
    for cand in ("DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(cand, int(u * 0.42))
            break
        except OSError:
            continue
    if font:
        bb = d.textbbox((0, 0), "Te", font=font)
        cx, cy = 0.50 * u, 0.50 * u
        d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]),
               "Te", font=font, fill=255)
    rgba = np.zeros((u, u, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = np.asarray(m)
    Image.fromarray(rgba, "RGBA").resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for fname, asset in MS_ICONS.items():
        enc = "/".join(urllib.parse.quote(s) for s in asset.split("/"))
        png = cairosvg.svg2png(bytestring=_get(MS.format(enc)),
                               output_width=RENDER_PX, output_height=RENDER_PX)
        (out / f"{fname}.png").write_bytes(png)
        print(f"  {fname}.png  <- ms-fluent/{asset.split('/')[0]}")
    if (out / "teams_logo.png").exists():
        print("  teams_logo.png  <- committed asset (left as-is)")
    else:
        _draw_teams_logo(out / "teams_logo.png")
        print("  teams_logo.png  <- drawn (generic chat-bubble + T)")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
