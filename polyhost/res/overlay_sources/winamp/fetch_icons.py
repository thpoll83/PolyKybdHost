#!/usr/bin/env python3
"""Fetch the Winamp shortcut icons.

Icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), both through `icon_fetch`. Where the action is the same as in the
foobar2000 and VLC sets (open files, save playlist, open a URL), the same glyph
is used. The ESC mark is the Winamp logo (the winamp.com favicon) reduced to a
32x32 1-bit trace, dark pixels lit. See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/winamp/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

FLUENT = {
    # --- transport ---
    "previous":     "Previous",
    "play":         "Play",
    "pause":        "Pause",
    "stop":         "Stop",
    "next":         "Next",
    "rewind":       "Rewind",
    "forward":      "Fast Forward",
    "startlist":    "Arrow Previous",
    "endlist":      "Arrow Next",
    "stopafter":    "ms:stop_circle",
    "fadeout":      "ms:music_off",
    "volumeup":     "ms:volume_up",
    "volumedown":   "ms:volume_down",
    "repeat":       "Arrow Repeat All",
    "shuffle":      "ms:shuffle",
    "manualadv":    "ms:touch_app",
    # --- open, playlist, jump ---
    "openfile":     "Document",
    "openfolder":   "Folder Open",
    "openurl":      "Globe",
    "openplaylist": "ms:file_open",
    "saveplaylist": "Save",
    "jumpfile":     "Search",
    "jumptime":     "Clock",
    "fileinfo":     "Tag",
    "addbookmark":  "Bookmark Add",
    "bookmarks":    "Bookmark Multiple",
    # --- windows ---
    "mainwindow":   "ms:web_asset",
    "playlisted":   "ms:queue_music",
    "equalizer":    "ms:tune",
    "video":        "Video",
    "fullscreen":   "Full Screen Maximize",
    "windowshade":  "ms:unfold_less",
    "doublesize":   "ms:open_in_full",
    "nextwindow":   "ms:select_window",
    "closewindow":  "Dismiss",
    "minimize":     "ms:minimize",
    "mainmenu":     "Navigation",
    "newinstance":  "Window New",
    "quit":         "Power",
    # --- options and plug-ins ---
    "preferences":  "Settings",
    "skins":        "ms:palette",
    "refreshskin":  "Arrow Clockwise",
    "timemode":     "ms:timer",
    "visselect":    "ms:graphic_eq",
    "visconfig":    "ms:display_settings",
    "vistoggle":    "ms:bar_chart",
    "help":         "Question Circle",
    "about":        "Info",
}


# winamp.com's favicon is the Winamp logo. Google's favicon service serves it.
WINAMP_ICON_URL = "https://www.google.com/s2/favicons?domain=winamp.com&sz=256"
WINAMP_DARK_LUMA = 128


def _winamp_mark(dest: Path, px: int = 32) -> None:
    """The Winamp logo as a px*px 1-bit trace: fitted into the square, pixels
    at luma 128 or darker lit. Drawn at the keycap size so the generator copies
    it 1:1."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    import io
    import urllib.request

    from PIL import Image
    req = urllib.request.Request(WINAMP_ICON_URL, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read())).convert("RGBA")
    white = Image.new("RGBA", icon.size, "white")
    white.alpha_composite(icon)
    src = white.convert("L")
    scale = px / max(src.size)
    fitted = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))),
                        Image.LANCZOS)
    square = Image.new("L", (px, px), 255)
    square.paste(fitted, ((px - fitted.width) // 2, (px - fitted.height) // 2))
    a = square.point(lambda v: 255 if v <= WINAMP_DARK_LUMA else 0)
    Image.merge("RGBA", (a, a, a, a)).save(dest)
    print(f"  {dest.name}  <- Winamp logo, 1-bit trace")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    _winamp_mark(out / "winamp.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
