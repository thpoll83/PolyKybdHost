#!/usr/bin/env python3
"""Fetch + render the Cisco Webex shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The ESC mark is the Webex
logo from Simple Icons (CC0 artwork; nominative use, see `../brand_marks.py`).

    pip install cairosvg
    python polyhost/res/overlay_sources/webex/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

FLUENT = {
    # --- general ---
    "search": "Search",
    "back": "Arrow Left",
    "forward": "Arrow Right",
    "tabmessaging": "Chat Multiple",
    "tabteams": "People Team",
    "tabcontacts": "Contact Card",
    "tabcalling": "Call",
    "tabmeetings": "Video",
    "tabinsights": "Data Pie",
    "tabvoicemail": "ms:voicemail",
    "tabwhiteboards": "Whiteboard",
    "health": "Heart Pulse",
    "settings": "Settings",
    "assistant": "Sparkle",
    "diagnostics": "Stethoscope",
    "navmenu": "Navigation",
    "shortcuts": "Keyboard",
    "signout": "Sign Out",
    # --- messaging ---
    "findinspace": "ms:manage_search",
    "newdm": "Chat Add",
    "newspace": "Add Square",
    "allspaces": "Apps List",
    "notifications": "Alert",
    "drafts": "Drafts",
    "unread": "ms:mark_chat_unread",
    "dmlist": "Person Chat",
    "favorites": "Star",
    "mentionsme": "ms:alternate_email",
    "mentionsall": "ms:groups",
    "flagged": "Flag",
    "spacemessages": "Chat",
    "spacecontent": "Folder",
    "peopletab": "People",
    "linkstab": "Link Multiple",
    "leavespace": "ms:logout",
    "addpeople": "Person Add",
    "stickers": "Sticker",
    "gif": "Gif",
    "emoji": "Emoji",
    "attach": "Attach",
    "prevspace": "Arrow Up",
    "nextspace": "Arrow Down",
    "collapse": "ms:unfold_less",
    "expand": "ms:unfold_more",
    "newwhiteboard": "ms:note_stack_add",
    "spacewhiteboards": "ms:dashboard",
    "jumpnew": "ms:vertical_align_bottom",
    "roomlink": "ms:meeting_room",
    "capture": "Screenshot",
    "capturehide": "ms:screenshot_region",
    "favorite": "Star Add",
    "callperson": "Call Add",
    "gototeam": "ms:groups_2",
    "reload": "Arrow Clockwise",
    "spacesettings": "ms:tune",
    "notifyall": "ms:notifications_active",
    "newmessage": "Compose",
    "newreply": "Arrow Reply",
    "copyspace": "Copy",
    "focusconv": "ms:forum",
    "compose": "ms:edit",
    "quickmsg": "ms:quickreply",
    # --- formatting ---
    "link": "Link",
    "markdown": "ms:markdown",
    "h1": "ms:format_h1",
    "h2": "ms:format_h2",
    "h3": "ms:format_h3",
    # --- calls and meetings ---
    "mute": "Mic Off",
    "camera": "Video",
    "endcall": "Call End",
    "answer": "Call Checkmark",
    "answermsg": "ms:sms",
    "decline": "Call Dismiss",
    "callingdock": "ms:dock_to_bottom",
    "hold": "Call Pause",
    "highlightcall": "ms:highlight_text_cursor",
    "transfer": "Call Forward",
    "dialpad": "Dialpad",
    "smartaudio": "ms:graphic_eq",
    "share": "Share Screen Start",
    "sharefile": "Document Arrow Up",
    "sharebrowser": "Globe",
    "whiteboard": "Whiteboard",
    "pauseshare": "ms:pause_presentation",
    "stopshare": "Share Screen Stop",
    "videoview": "ms:picture_in_picture_alt",
    "cleanmode": "ms:hide_source",
    "controls": "ms:toolbar",
    "menubar": "ms:menu",
    "floating": "ms:select_window_2",
    "annotate": "Pen",
    "stopannotate": "Pen Off",
    "clearannot": "Eraser",
    "fullscreen": "Full Screen Maximize",
    "thumbnails": "ms:view_sidebar",
    "raisehand": "Hand Right",
    "chat": "Chat",
    "chatnotify": "ms:speaker_notes",
    "interpret": "Translate",
    "outlang": "ms:g_translate",
    "videos": "Video Person",
    "novideo": "ms:no_photography",
    "names": "ms:badge",
    "muteall": "ms:volume_off",
    "lowerhands": "ms:do_not_touch",
    "lock": "Lock Closed",
    "remove": "Person Delete",
    "admit": "ms:how_to_reg",
    "allowshare": "ms:screen_share",
    "privileges": "Shield Person",
    "addguest": "Person Arrow Right",
    "remote": "ms:mouse",
    "captions": "Closed Caption",
    "captionmenu": "ms:subtitles",
    "notification": "ms:notification_important",
    "reactions": "Emoji Add",
    "thumbsup": "Thumb Like",
    "clap": "Hand Wave",
    "haha": "Emoji Laugh",
    "celebrate": "ms:celebration",
    "love": "Heart",
    # --- shared content (Webex Meetings) ---
    "sync": "Arrow Sync",
    "transferfile": "ms:upload_file",
    "addpage": "Document Add",
    "fit": "ms:fit_screen",
    "fitwidth": "ms:fit_page_width",
    "rotateleft": "Arrow Rotate Counterclockwise",
    "rotateright": "Arrow Rotate Clockwise",
    "closefile": "Document Dismiss",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    brand_marks.ensure(out / "webex.png", "webex")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
