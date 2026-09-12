#!/usr/bin/env python3
"""Fetch + render the Windows Terminal shortcut icons (reproducible source step).

Style route: **all shortcut icons come from Microsoft Fluent UI System Icons
(MIT)** — the house style across every PolyKybd app overlay, and license-clean
against the GPL-3.0-or-later host. The ESC **program mark** is NOT baked here -- it
comes from the curated generic `mdi:console` (`polyhost/res/app_icons.yaml`),
a `>_` that carries no trademark. It replaced a framed `>_` drawn here; the
shared `../prompt_glyph.py` that drawing moved into is still used, by WinSCP's
open-terminal key.

Shortcuts come from the app's OWN defaults — `defaults.json` in
microsoft/terminal — not from a docs page, so they are authoritative and
complete. See SOURCES.md.

Each icon renders to a 96x96 RGBA PNG; the generator's `luma` mode keeps the
linework at 1-bit. Re-running reproduces icons/*.png.

    pip install cairosvg
    python polyhost/res/overlay_sources/windowsterminal/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import number_badge  # noqa: E402

RENDER_PX = 96

# action filename -> Microsoft Fluent System Icon folder (all MIT).
# ⚠️ The asset path is derived, not guessed: `ic_fluent_<snake(folder)>_24_regular.svg`.
# Every name below was probed against raw.githubusercontent.com before use --
# plausible-looking names 404 often (there is no "Pane Close", no "Text Select",
# no "Chevron Double Up").
MS_ICONS = {
    # tabs & windows
    "newtab":       "Tab Add",
    "newwindow":    "Window New",
    "duptab":       "Square Multiple",
    "closepane":    "Dismiss Square",
    "tab":          "Tab",
    "tabdropdown":  "Chevron Down",
    "nexttab":      "Arrow Right",
    "prevtab":      "Arrow Left",
    # panes
    "splitdown":    "Split Horizontal",     # a box divided top/bottom
    "splitright":   "Split Vertical",       # two boxes side by side
    "resizepane":   "Resize",
    "focusup":      "Arrow Up",
    "focusdown":    "Arrow Down",
    "focusleft":    "Arrow Left",
    "focusright":   "Arrow Right",
    # edit / clipboard
    "copy":         "Copy",
    "paste":        "Clipboard Paste",
    "selectall":    "Select All On",
    "markmode":     "Highlight",
    "find":         "Search",
    "clear":        "Broom",
    # scrolling
    "scrollup":     "Arrow Sort Up",
    "scrolldown":   "Arrow Sort Down",
    "pageup":       "Arrow Circle Up",
    "pagedown":     "Arrow Circle Down",
    "totop":        "Arrow Upload",         # arrow into a line
    "tobottom":     "Arrow Download",
    # view / app
    "palette":      "Apps List",
    "suggestions":  "Lightbulb",
    "settings":     "Settings",
    "settingsfile": "Code",
    "defaultsfile": "Document",
    "fullscreen":   "Full Screen Maximize",
    "sysmenu":      "Navigation",
    "fontbig":      "Font Increase",
    "fontsmall":    "Font Decrease",
    "fontreset":    "Text Font Size",
}



def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)

    icon_fetch.fluent(MS_ICONS, out)

    # Ctrl+Alt+<N> switches to tab N. The bare Fluent "Tab" glyph is an empty
    # rounded box and reads as nothing at 40 px, so the NUMBER goes inside it --
    # see number_badge for why that is one shared implementation.
    number_badge.numbered(out / "tab.png", "12345678", out, "tab")

    print(f"Wrote {len(MS_ICONS)} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
