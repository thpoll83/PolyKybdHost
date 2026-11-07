#!/usr/bin/env python3
"""Fetch the VICE shortcut icons.

Action icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), both through `icon_fetch`. The ESC mark is the VICE logo,
`data/common/vice-logo-black.svg` of the 3.10.0 release, which VICE installs
and distributes under its GPL-2.0-or-later. See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/vice/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.retroarch import fetch_icons as ra  # noqa: E402

LOGO_URL = ("https://raw.githubusercontent.com/VICE-Team/svn-mirror/3.10.0/"
            "vice/data/common/vice-logo-black.svg")
DRIVES = ("8", "9", "10", "11")   # drive-attach / drive-detach keys 8, 9, 0, 1
# Form-feed keys 3..6: file name, label, size. VICE's printers are CBM devices 4, 5
# and 6 (printerdrv/printer.h); the userport printer has no device number (its
# internal index is 3), so its key says USER, at 8 px to fit 36 px.
PRINTERS = (("3", "USER", 8), ("4", "4", 16), ("5", "5", 16), ("6", "6", 16))
LOGO_W = 40      # px wide: 40 x 11, still reads "VICE" and clears the Esc legend (x 2..27)

FLUENT = {
    "smartattach":   "ms:attach_file",
    "resetcpu":      "ms:restart_alt",
    "powercycle":    "ms:power_settings_new",
    "quit":          "ms:close",
    "driveattach":   "ms:hard_drive",
    "eject":         "ms:eject",
    "flipadd":       "ms:playlist_add",
    "flipremove":    "ms:playlist_remove",
    "flipnext":      "ms:arrow_forward",
    "flipprev":      "ms:arrow_back",
    "tape":          "ms:voicemail",
    "cartattach":    "ms:memory",
    "freeze":        "ms:ac_unit",
    "formfeed":      "ms:print",
    "copy":          "Copy",
    "paste":         "Clipboard Paste",
    "snapload":      "Folder Open",
    "snapsave":      "Save",
    "quickload":     "ms:file_open",
    "quicksave":     "ms:save_as",
    "milestone":     "ms:flag",
    "milestoneback": "ms:history",
    "record":        "ms:fiber_manual_record",
    "stop":          "ms:stop",
    "screenshot":    "Camera",
    "monitor":       "ms:terminal",
    "fullscreen":    "ms:fullscreen",
    "restoredisp":   "ms:fit_screen",
    "toolbar":       "ms:toolbar",
    "warp":          "ms:fast_forward",
    "pause":         "ms:pause",
    "frameadv":      "ms:skip_next",
    "mousegrab":     "ms:mouse",
    "swapports":     "ms:swap_horiz",
    "keysetjoy":     "ms:sports_esports",
    "settings":      "Settings",
    "settingsreset": "ms:settings_backup_restore",
}


def vice_mark(dest: Path, width: int = LOGO_W) -> None:
    """The VICE wordmark at `width` px, 1 bit (its shapes lit), cropped to ink."""
    import io

    import cairosvg
    import numpy as np
    from PIL import Image
    png = cairosvg.svg2png(bytestring=cnc._get(LOGO_URL), output_width=width)
    m = np.asarray(Image.open(io.BytesIO(png)).convert("RGBA").getchannel("A")) > 127
    ys, xs = np.nonzero(m)
    cnc._save_mask(m[ys.min():ys.max() + 1, xs.min():xs.max() + 1], dest)


def symbol(src: Path, w: int, h: int):
    """`src`'s ink fitted into `w` x `h`, 1 bit.

    BOX (area average), not LANCZOS: Lanczos rings at each edge, and after the
    1-bit cut a straight edge then wobbles by a pixel. An area average gives
    every pixel along a straight edge the same coverage, so it cuts the same."""
    import numpy as np
    from PIL import Image
    a = Image.open(src).convert("RGBA").getchannel("A")
    a = a.crop(a.getbbox())
    k = min(w / a.width, h / a.height)
    return np.asarray(a.resize((max(1, round(a.width * k)), max(1, round(a.height * k))),
                               Image.BOX)) > 127


def stacked(top, bottom, dest: Path, w: int = 36, h: int = 32, gap: int = 2) -> None:
    """1-bit `top` mask over 1-bit `bottom` mask, both centred, drawn `w` x `h`."""
    import numpy as np
    m = np.zeros((h, w), bool)
    x = (w - top.shape[1]) // 2
    m[:top.shape[0], x:x + top.shape[1]] = top
    y, x = top.shape[0] + gap, (w - bottom.shape[1]) // 2
    m[y:y + bottom.shape[0], x:x + bottom.shape[1]] = bottom
    cnc._save_mask(m, dest)


def numbered(src: Path, label: str, dest: Path, w: int = 36, h: int = 32, gap: int = 2,
             px: int = 16) -> None:
    """`src`'s symbol under `label` (Press Start 2P, `px`), drawn 1 bit at `w` x `h`.
    The drive keys draw 0 and 1 for drives 10 and 11, so the icon names the device."""
    text = ra._text_mask(label, px)
    stacked(text, symbol(src, w, h - text.shape[0] - gap), dest, w, h, gap)


def joystick():
    """A 16 x 15 one-button joystick, drawn pixel by pixel: Material's joystick
    turns to a blur at this size."""
    import numpy as np
    from PIL import Image, ImageDraw
    im = Image.new("1", (16, 15), 0)
    d = ImageDraw.Draw(im)
    d.ellipse((5, 0, 10, 5), fill=1)                          # ball
    d.rectangle((7, 6, 8, 9), fill=1)                         # shaft
    d.rectangle((2, 8, 3, 9), fill=1)                         # fire button
    d.rounded_rectangle((0, 10, 15, 14), radius=2, fill=1)    # base
    return np.array(im, bool)


def window_in_frame(out: Path, dest: Path, size: int = 20) -> None:
    """Full-screen corners around a small window with a title bar: full screen
    WITH the window decorations."""
    import numpy as np
    corners = symbol(out / "fullscreen.png", 36, 32)
    win = symbol(out / "toolbar.png", size, size)
    m = np.zeros((32, 36), bool)
    y, x = (32 - corners.shape[0]) // 2, (36 - corners.shape[1]) // 2
    m[y:y + corners.shape[0], x:x + corners.shape[1]] = corners
    y, x = (32 - win.shape[0]) // 2, (36 - win.shape[1]) // 2
    m[y:y + win.shape[0], x:x + win.shape[1]] |= win
    cnc._save_mask(m, dest)


def composites(out: Path) -> None:
    """Every icon this set draws from other icons (no network)."""
    for d in DRIVES:
        numbered(out / "driveattach.png", d, out / f"drive{d}.png")
        numbered(out / "eject.png", d, out / f"eject{d}.png")
    for name, label, px in PRINTERS:
        numbered(out / "formfeed.png", label, out / f"printer{name}.png", px=px)
    stacked(symbol(out / "tape.png", 36, 14), symbol(out / "eject.png", 36, 16),
            out / "tapedetach.png")
    stacked(symbol(out / "cartattach.png", 36, 14), symbol(out / "eject.png", 36, 16),
            out / "cartdetach.png")
    stacked(joystick(), symbol(out / "swapports.png", 36, 15), out / "swapjoy.png")
    window_in_frame(out, out / "decorframe.png")
    numbered(out / "monitor.png", "MON", out / "monterm.png", px=8)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    composites(out)
    vice_mark(out / "vice.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
