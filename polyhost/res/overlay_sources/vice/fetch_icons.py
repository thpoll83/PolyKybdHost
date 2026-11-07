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
LOGO_W = 52      # px wide; the wordmark is 3.6:1, so 15 px high, and reads "VICE"

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


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    vice_mark(out / "vice.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
