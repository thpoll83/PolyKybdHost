#!/usr/bin/env python3
"""Fetch + render the Microsoft Teams shortcut icons (reproducible).

Most glyphs are Microsoft Fluent UI System Icons (MIT), the native style for a
Microsoft app; the rest are Material Symbols (Apache-2.0) through `MORE`, and the
app-bar and chat-tab keys are numbered glyphs from `../number_badge.py`. Both
licences fit the host's GPL-3.0-or-later. Rendered to 96x96 RGBA PNG;
the generator's `luma` mode keeps the linework at 1-bit. The program icon (ESC)
is a generic drawn chat-bubble mark with a "T" (no Microsoft Teams logo) — drop a
real Teams logo as icons/teams_logo.png to override (committed assets untouched).

    pip install cairosvg
    python polyhost/res/overlay_sources/teams/fetch_icons.py
"""
from __future__ import annotations

import sys
import urllib.parse
import urllib.request
from pathlib import Path

import cairosvg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch, number_badge  # noqa: E402

RENDER_PX = 96
MS = "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/assets/{}"

# All probed against raw.githubusercontent.com (no 404) on 2026-06-15.
MS_ICONS = {
    # --- general (Ctrl) ---
    "search": "Search/SVG/ic_fluent_search_24_regular.svg",
    "newchat": "Chat Add/SVG/ic_fluent_chat_add_24_regular.svg",
    "settings": "Settings/SVG/ic_fluent_settings_24_regular.svg",
    "shortcuts": "Keyboard/SVG/ic_fluent_keyboard_24_regular.svg",
    "zoomin": "Zoom In/SVG/ic_fluent_zoom_in_24_regular.svg",
    "zoomout": "Zoom Out/SVG/ic_fluent_zoom_out_24_regular.svg",

    "attach": "Attach/SVG/ic_fluent_attach_24_regular.svg",
    # --- app-bar navigation (Ctrl 1..6, default order) ---
    "chat": "Chat/SVG/ic_fluent_chat_24_regular.svg",
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


# Glyphs the 2026-10 refresh added, through the shared helper (Fluent folder
# names, `ms:` for Material Symbols, Apache-2.0).
MORE = {
    "help": "ms:help",
    "newwindowchat": "ms:open_in_new",
    "report": "ms:bug_report",
    "gotochat": "ms:jump_to_element",
    "pinontop": "ms:keep",
    "openwindow": "ms:open_in_browser",
    "focuslist": "ms:list",
    "focusmsg": "ms:forum",
    "compose": "ms:edit",
    "history": "ms:history",
    "nextsection": "ms:keyboard_tab",
    "prevsection": "ms:keyboard_tab_rtl",
    "back": "ms:arrow_back",
    "forward": "ms:arrow_forward",
    "movechatup": "ms:arrow_upward",
    "movechatdown": "ms:arrow_downward",
    "collapse": "ms:unfold_less",
    "jumpnew": "ms:vertical_align_bottom",
    "find": "ms:find_in_page",
    "details": "ms:info",
    "react": "ms:add_reaction",
    "unread": "ms:mark_chat_unread",
    "mentions": "ms:alternate_email",
    "channels": "ms:tag",
    "meetingchats": "ms:video_chat",
    "clearfilters": "ms:filter_alt_off",
    "send": "ms:send",
    "paragraph": "ms:format_paragraph",
    "quote": "ms:format_quote",
    "h1": "ms:format_h1",
    "h2": "ms:format_h2",
    "h3": "ms:format_h3",
    "strike": "ms:strikethrough_s",
    "copilot": "ms:auto_awesome",
    "videorec": "ms:videocam",
    "loop": "ms:all_inclusive",
    "link": "ms:link",
    "inlinecode": "ms:code",
    "codeblock": "ms:code_blocks",
    "insertcode": "ms:data_object",
    "endcall": "ms:call_end",
    "speaker": "ms:volume_up",
    "tempunmute": "ms:mic",
    "sharetoolbar": "ms:toolbar",
    "admit": "ms:how_to_reg",
    "schedule": "ms:edit_calendar",
    "joinmeeting": "ms:login",
    "joinfromtoast": "ms:notifications_active",
    "meetingchat": "ms:chat",
    "fullscreen": "ms:fullscreen",
    "sharezoomin": "ms:zoom_in",
    "sharezoomout": "ms:zoom_out",
    "sharezoomreset": "ms:fit_screen",
    "resetzoom": "ms:restart_alt",
    "panup": "ms:keyboard_double_arrow_up",
    "pandown": "ms:keyboard_double_arrow_down",
    "panleft": "ms:keyboard_double_arrow_left",
    "panright": "ms:keyboard_double_arrow_right",
    "dayview": "ms:calendar_view_day",
    "workweek": "ms:view_week",
    "weekview": "ms:calendar_view_week",
    "monthview": "ms:calendar_view_month",
    "agenda": "ms:view_agenda",
    "prevperiod": "ms:chevron_left",
    "nextperiod": "ms:chevron_right",
    "today": "ms:today",
    # bases for the numbered glyphs: app-bar position and chat-header tab
    "_appbase": "Square",
    "_tabbase": "ms:chat_bubble",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for fname, asset in MS_ICONS.items():
        enc = "/".join(urllib.parse.quote(s) for s in asset.split("/"))
        png = cairosvg.svg2png(bytestring=_get(MS.format(enc)),
                               output_width=RENDER_PX, output_height=RENDER_PX)
        (out / f"{fname}.png").write_bytes(png)
        print(f"  {fname}.png  <- ms-fluent/{asset.split('/')[0]}")
    icon_fetch.fluent(MORE, out)
    # The app-bar keys open the Nth app of the user's own rail, so the number
    # is the information; the chat-header keys open the Nth tab of a chat.
    number_badge.numbered(out / "_appbase.png", "123456789", out, "app")
    # The bubble body sits in the top two thirds, so the digit goes there.
    number_badge.numbered(out / "_tabbase.png", "123456789", out, "tab",
                          size=0.40, centre=(0.52, 0.42))
    if (out / "teams_logo.png").exists():
        print("  teams_logo.png  <- committed asset (left as-is)")
    else:
        _draw_teams_logo(out / "teams_logo.png")
        print("  teams_logo.png  <- drawn (generic chat-bubble + T)")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
