#!/usr/bin/env python3
"""Fetch and render the icons of the social and messaging overlay sets.

One icon folder serves four specs, because they share most of their actions
(reply, like, repost, new post, search, next and previous item):

* `whatsapp_web.yaml`  WhatsApp Web (web.whatsapp.com)
* `whatsapp.yaml`      the WhatsApp desktop apps (Windows, macOS)
* `x.yaml`             X (x.com)
* `mastodon.yaml`      Mastodon's web app on the largest servers

Three kinds of icon are in `icons/`:

* Fetched: Microsoft Fluent UI System Icons (MIT) by folder name, or Google
  Material Symbols (Apache-2.0) for an `ms:` name. A re-run may overwrite them.
* Numbered: `chat1.png` .. `chat9.png` (WhatsApp Ctrl+1..9, chat by position)
  and `column1.png` .. `column9.png` (Mastodon 1..9, focus column), drawn with
  `../number_badge.py`.
* The ESC program marks `whatsapp.png`, `x.png` and `mastodon.png`: each
  brand's monochrome logo from Simple Icons (artwork CC0-1.0,
  `../brand_marks.py`). A committed file is left as-is.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/social/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand_marks, icon_fetch, number_badge  # noqa: E402

FLUENT = {
    # --- timeline (X, Mastodon) ---
    "nextpost": "Arrow Down",
    "prevpost": "Arrow Up",
    "pagedown": "ms:keyboard_double_arrow_down",
    "top": "ms:vertical_align_top",
    "loadnew": "ms:dynamic_feed",
    "loadmore": "ms:expand_circle_down",
    "openpost": "Open",
    "media": "Image",
    "back": "Arrow Left",
    "help": "Question Circle",
    "search": "Search",
    "zoomreset": "ms:fit_screen",
    # --- post actions ---
    "reply": "Arrow Reply",
    "like": "Heart",
    "favourite": "Star",
    "repost": "Arrow Repeat All",
    "quote": "ms:format_quote",
    "mention": "ms:alternate_email",
    "share": "Share",
    "muteaccount": "Speaker Mute",
    "profile": "Person Circle",
    "translate": "Translate",
    "contentwarning": "Eye Off",
    "sensitive": "ms:hide_image",
    "newpost": "Compose",
    "newdm": "Mail Add",
    "send": "Send",
    # --- chats (WhatsApp) ---
    "unread": "ms:mark_chat_unread",
    "mutechat": "Alert Off",
    "archive": "Archive",
    "pin": "Pin",
    "deletechat": "Delete",
    "block": "Person Prohibited",
    "newchat": "Chat Add",
    "newgroup": "People Add",
    "searchchat": "ms:manage_search",
    "extsearch": "ms:travel_explore",
    "nextchat": "Arrow Circle Down",
    "prevchat": "Arrow Circle Up",
    "chatinfo": "Info",
    "lock": "Lock Closed",
    "emoji": "Emoji",
    "gif": "Gif",
    "sticker": "Sticker",
    # --- messages (WhatsApp desktop) ---
    "replyprivate": "ms:quickreply",
    "forward": "Arrow Forward",
    "editlast": "Edit",
    "star": "Star Add",
    "attach": "Attach",
    "recordvoice": "Mic",
    "pausevoice": "ms:pause_circle",
    "speedup": "ms:speed",
    "speeddown": "ms:slow_motion_video",
    # base glyphs of the numbered sets (not bound themselves)
    "_chatbase": "Chat Empty",
    "_columnbase": "ms:crop_portrait",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    n += number_badge.numbered(out / "_chatbase.png", "123456789", out, "chat",
                               size=0.50, centre=(0.53, 0.47))
    n += number_badge.numbered(out / "_columnbase.png", "123456789", out, "column",
                               size=0.50, centre=(0.50, 0.50))
    for slug in ("whatsapp", "x", "mastodon"):
        brand_marks.ensure(out / f"{slug}.png", slug)
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
