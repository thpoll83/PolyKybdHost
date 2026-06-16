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
    # --- added (coverage audit 2026-06) ---
    "filter": "Filter/SVG/ic_fluent_filter_24_regular.svg",
    "important": "Important/SVG/ic_fluent_important_24_regular.svg",
    "reply": "Arrow Reply/SVG/ic_fluent_arrow_reply_24_regular.svg",
}


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "polykybd"}), timeout=30).read()


def _draw_teams_logo(path: Path) -> None:
    """Generic, license-clean Teams program mark (no Microsoft logo). Uses the
    same generic 'Office document' style as the Word mark — a 90deg-rotated
    trapezoid page on the left with a letter knocked out (negative space), plus
    a few text lines on the right — but stamped with a 'T' instead of a 'W', so
    Teams sits visually with the other Office apps. White shape on transparent
    (alpha = the lit shape) -> program_icon_mode: alpha."""
    ss = 4
    u = RENDER_PX * ss
    px = lambda n: n * ss          # final px -> supersampled px

    # rounded rectangle around the text lines (right), with the lines inside
    right = Image.new("L", (u, u), 0)
    dr = ImageDraw.Draw(right)
    dr.rounded_rectangle([0.50 * u, 0.24 * u, 0.93 * u, 0.76 * u],
                         radius=0.10 * u, outline=255, width=px(3))
    for y in (0.36, 0.50, 0.64):
        dr.line([(0.58 * u, y * u), (0.86 * u, y * u)], fill=255, width=int(u * 0.05))

    # left trapezoid (parallel vertical sides, right side taller -> looks rotated),
    # extended right so it overlaps well into the rounded rect and hides its left edge
    right_x = 0.58 * u
    trap = Image.new("L", (u, u), 0)
    ImageDraw.Draw(trap).polygon(
        [(0.10 * u, 0.20 * u), (right_x, 0.11 * u),
         (right_x, 0.89 * u), (0.10 * u, 0.80 * u)], fill=255)
    # 'T' to knock out of the trapezoid
    tmask = Image.new("L", (u, u), 0)
    dt = ImageDraw.Draw(tmask)
    font = None
    for cand in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(cand, int(u * 0.40))
            break
        except OSError:
            continue
    if font:
        bb = dt.textbbox((0, 0), "T", font=font)
        cx, cy = (0.10 * u + right_x) / 2, 0.50 * u
        dt.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]),
                "T", font=font, fill=255)
    knock = np.where(np.asarray(tmask) > 127, 0, np.asarray(trap)).astype(np.uint8)

    # trapezoid drawn on top of the rounded rect -> its solid fill swallows the
    # rect's left edge (max() merges the overlap into one lit shape)
    alpha = np.maximum(np.asarray(right), knock)
    rgba = np.zeros((u, u, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = alpha
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
