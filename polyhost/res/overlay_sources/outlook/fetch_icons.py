#!/usr/bin/env python3
"""Fetch + render the Microsoft Outlook shortcut icons (reproducible).

All glyphs are Microsoft Fluent UI System Icons (MIT) — native style for a MS app,
license-clean (host is GPL-2.0). Rendered to 96x96 RGBA PNG; the generator's
`luma` mode keeps the linework at 1-bit. The program icon (ESC) is a generic mark
drawn in code (no Microsoft logo): the Word-style trapezoid + knocked-out 'O' +
rounded rect with text lines.

    pip install cairosvg
    python polyhost/res/overlay_sources/outlook/fetch_icons.py
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

MS_ICONS = {
    "new": "Mail Add/SVG/ic_fluent_mail_add_24_regular.svg",
    "reply": "Arrow Reply/SVG/ic_fluent_arrow_reply_24_regular.svg",
    "forward": "Arrow Forward/SVG/ic_fluent_arrow_forward_24_regular.svg",
    "send": "Send/SVG/ic_fluent_send_24_regular.svg",
    "print": "Print/SVG/ic_fluent_print_24_regular.svg",
    "save": "Save/SVG/ic_fluent_save_24_regular.svg",
    "search": "Search/SVG/ic_fluent_search_24_regular.svg",
    "markread": "Mail Read/SVG/ic_fluent_mail_read_24_regular.svg",
    "markunread": "Mail Unread/SVG/ic_fluent_mail_unread_24_regular.svg",
    "hyperlink": "Link/SVG/ic_fluent_link_24_regular.svg",
    "bold": "Text Bold/SVG/ic_fluent_text_bold_24_regular.svg",
    "italic": "Text Italic/SVG/ic_fluent_text_italic_24_regular.svg",
    "mailview": "Mail Inbox/SVG/ic_fluent_mail_inbox_24_regular.svg",
    "calview": "Calendar/SVG/ic_fluent_calendar_24_regular.svg",
    "peopleview": "People/SVG/ic_fluent_people_24_regular.svg",
    "tasksview": "Tasks App/SVG/ic_fluent_tasks_app_24_regular.svg",
    "replyall": "Arrow Reply All/SVG/ic_fluent_arrow_reply_all_24_regular.svg",
    "newappt": "Calendar Add/SVG/ic_fluent_calendar_add_24_regular.svg",
    "newcontact": "Person Add/SVG/ic_fluent_person_add_24_regular.svg",
    "newtask": "Task List Add/SVG/ic_fluent_task_list_add_24_regular.svg",
    "flag": "Flag/SVG/ic_fluent_flag_24_regular.svg",
    "delete": "Delete/SVG/ic_fluent_delete_24_regular.svg",
    "sendrecv": "Arrow Sync/SVG/ic_fluent_arrow_sync_24_regular.svg",
    "notes": "Note/SVG/ic_fluent_note_24_regular.svg",
    "folderlist": "Apps List/SVG/ic_fluent_apps_list_24_regular.svg",
    "shortcuts": "Star/SVG/ic_fluent_star_24_regular.svg",
    "nextmsg": "Arrow Down/SVG/ic_fluent_arrow_down_24_regular.svg",
    "prevmsg": "Arrow Up/SVG/ic_fluent_arrow_up_24_regular.svg",
    "gotodate": "Calendar Arrow Right/SVG/ic_fluent_calendar_arrow_right_24_regular.svg",
    "hangindent": "Text Indent Increase/SVG/ic_fluent_text_indent_increase_24_regular.svg",
    "hyphen": "Subtract/SVG/ic_fluent_subtract_24_regular.svg",
}


def _draw_outlook_logo(path: Path) -> None:
    """Generic, license-clean 'Outlook' program icon (no Microsoft logo): the
    Word-style mark (trapezoid + knocked-out letter + rounded rect with text
    lines) with the letter 'O'. White shape on transparent (alpha = lit shape)
    -> `program_icon_mode: alpha`."""
    ss = 4
    u = RENDER_PX * ss
    px = lambda n: n * ss

    right = Image.new("L", (u, u), 0)
    dr = ImageDraw.Draw(right)
    dr.rounded_rectangle([0.50 * u, 0.24 * u, 0.93 * u, 0.76 * u],
                         radius=0.10 * u, outline=255, width=px(3))
    for y in (0.36, 0.50, 0.64):
        dr.line([(0.58 * u, y * u), (0.86 * u, y * u)], fill=255, width=int(u * 0.05))

    right_x = 0.58 * u
    trap = Image.new("L", (u, u), 0)
    ImageDraw.Draw(trap).polygon(
        [(0.10 * u, 0.20 * u), (right_x, 0.11 * u),
         (right_x, 0.89 * u), (0.10 * u, 0.80 * u)], fill=255)
    wmask = Image.new("L", (u, u), 0)
    dw = ImageDraw.Draw(wmask)
    font = None
    for cand in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(cand, int(u * 0.34))
            break
        except OSError:
            continue
    if font:
        bb = dw.textbbox((0, 0), "O", font=font)
        cx, cy = (0.10 * u + right_x) / 2, 0.50 * u
        dw.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]),
                "O", font=font, fill=255)
    knock = np.where(np.asarray(wmask) > 127, 0, np.asarray(trap)).astype(np.uint8)

    alpha = np.maximum(np.asarray(right), knock)
    rgba = np.zeros((u, u, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = alpha
    Image.fromarray(rgba, "RGBA").resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "polykybd"}), timeout=30).read()


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for fname, asset in MS_ICONS.items():
        enc = "/".join(urllib.parse.quote(s) for s in asset.split("/"))
        png = cairosvg.svg2png(bytestring=_get(MS.format(enc)),
                               output_width=RENDER_PX, output_height=RENDER_PX)
        (out / f"{fname}.png").write_bytes(png)
        print(f"  {fname}.png  <- ms-fluent/{asset.split('/')[0]}")
    if (out / "outlook.png").exists():
        print("  outlook.png  <- committed asset (left as-is)")
    else:
        _draw_outlook_logo(out / "outlook.png")
        print("  outlook.png  <- generic drawn (trapezoid + knocked-out O + text lines)")
    print(f"Wrote {len(MS_ICONS) + 1} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
