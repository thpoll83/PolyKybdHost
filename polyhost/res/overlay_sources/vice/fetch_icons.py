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

LOGO_URL = ("https://raw.githubusercontent.com/VICE-Team/svn-mirror/3.10.0/"
            "vice/data/common/vice-logo-black.svg")
DRIVES = ("8", "9", "10", "11")   # drive-attach / drive-detach keys 8, 9, 0, 1
LOGO_W = 40      # px wide: 40 x 11, still reads "VICE" and clears the Esc legend (x 2..27)

FLUENT = {
    "smartattach":   "ms:attach_file",
    "monitor":       "ms:terminal",
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
    "fullscreen":    "ms:fullscreen",
    "restoredisp":   "ms:fit_screen",
    "decorations":   "ms:web_asset",
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


def numbered(src: Path, label: str, dest: Path, w: int = 36, h: int = 32, gap: int = 2,
             px: int = 16) -> None:
    """`src`'s symbol under `label` (Press Start 2P, `px`), drawn 1 bit at `w` x `h`.
    The drive keys draw 0 and 1 for drives 10 and 11, so the icon names the drive."""
    import numpy as np
    from PIL import Image

    from polyhost.res.overlay_sources.retroarch import fetch_icons as ra
    text = ra._text_mask(label, px)
    a = Image.open(src).convert("RGBA").getchannel("A")
    a = a.crop(a.getbbox())
    k = min(w / a.width, (h - text.shape[0] - gap) / a.height)
    sym = np.asarray(a.resize((max(1, round(a.width * k)), max(1, round(a.height * k))),
                              Image.LANCZOS)) > 127
    m = np.zeros((h, w), bool)
    x = (w - text.shape[1]) // 2
    m[:text.shape[0], x:x + text.shape[1]] = text
    y, x = text.shape[0] + gap, (w - sym.shape[1]) // 2
    m[y:y + sym.shape[0], x:x + sym.shape[1]] = sym
    cnc._save_mask(m, dest)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    for d in DRIVES:
        numbered(out / "driveattach.png", d, out / f"drive{d}.png")
        numbered(out / "eject.png", d, out / f"eject{d}.png")
    vice_mark(out / "vice.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
