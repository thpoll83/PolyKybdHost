#!/usr/bin/env python3
"""Fetch + render the Windows Terminal shortcut icons (reproducible source step).

Style route: **all shortcut icons come from Microsoft Fluent UI System Icons
(MIT)** — the house style across every PolyKybd app overlay, and license-clean
against the GPL-3.0-or-later host. Windows Terminal's own product icon is
Microsoft trademark art, so the ESC **program mark is drawn here** instead: a
generic `>_` prompt in a rounded frame, which is the universal terminal mark and
carries no trademark.

Shortcuts come from the app's OWN defaults — `defaults.json` in
microsoft/terminal — not from a docs page, so they are authoritative and
complete. See SOURCES.md.

Each icon renders to a 96x96 RGBA PNG; the generator's `luma` mode keeps the
linework at 1-bit. Re-running reproduces icons/*.png.

    pip install cairosvg
    python polyhost/res/overlay_sources/windowsterminal/fetch_icons.py
"""
from __future__ import annotations

import urllib.parse
import urllib.request
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont

RENDER_PX = 96
MS = "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/assets/{}"

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


def _asset(folder: str) -> str:
    snake = folder.lower().replace(" ", "_").replace("-", "_")
    return f"{folder}/SVG/ic_fluent_{snake}_24_regular.svg"


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "polykybd"}), timeout=30).read()


def _draw_tab_number(base: Image.Image, digit: str, path: Path) -> None:
    """Composite `tab<N>`: the Fluent Tab box with the tab NUMBER inside it.

    ⚠️ The bare "Tab" glyph is an empty rounded box, and at 40 px on a keycap it
    reads as nothing at all -- the whole point of Ctrl+Alt+<N> is WHICH tab, so
    the number has to be in the picture. (Checked by rendering the overlay, not
    by reading the glyph name.)

    Composite rules, learned the hard way on the Word line-spacing set: a STATIC
    font size (auto-fitting per value renders the same digit at different sizes)
    and a fixed centre, so every digit in the family is placed identically.
    """
    img = base.copy()
    d = ImageDraw.Draw(img)
    # Liberation Sans is metric-compatible with Arial; real Arial is not installed.
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 52)
    # The Tab glyph's box is roughly the middle of the 96x96 canvas; centre the
    # digit on it rather than on the canvas, which sits a little low.
    d.text((RENDER_PX * 0.50, RENDER_PX * 0.56), digit, fill=(0, 0, 0, 255),
           font=font, anchor="mm")
    img.save(path)


def _draw_prompt_mark(path: Path) -> None:
    """Program mark: a rounded frame with a `>_` prompt inside.

    Drawn rather than downloaded because Windows Terminal's own icon is Microsoft
    trademark art. White on transparent, so the binding renders it with
    `mode: alpha` -- the alpha IS the shape.
    """
    ss = 4
    u = 256 * ss
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    frame = int(u * 0.055)
    d.rounded_rectangle([frame // 2, u * 0.14, u - frame // 2, u * 0.86],
                        radius=int(u * 0.10), outline=white, width=frame)
    # ">" chevron
    stroke = int(u * 0.065)
    d.line([(u * 0.26, u * 0.34), (u * 0.46, u * 0.50), (u * 0.26, u * 0.66)],
           fill=white, width=stroke, joint="curve")
    # "_" underscore
    d.line([(u * 0.53, u * 0.66), (u * 0.75, u * 0.66)], fill=white, width=stroke)
    img.resize((256, 256), Image.LANCZOS).save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)

    for fname, folder in MS_ICONS.items():
        asset = _asset(folder)
        enc = "/".join(urllib.parse.quote(s) for s in asset.split("/"))
        png = cairosvg.svg2png(bytestring=_get(MS.format(enc)),
                               output_width=RENDER_PX, output_height=RENDER_PX)
        (out / f"{fname}.png").write_bytes(png)
        print(f"  {fname}.png  <- ms-fluent/{folder}")

    # Ctrl+Alt+<N> switches to tab N -- one composite per digit, off the Tab glyph.
    tab_base = Image.open(out / "tab.png").convert("RGBA")
    for digit in "12345678":
        _draw_tab_number(tab_base, digit, out / f"tab{digit}.png")
    print("  tab1..tab8.png  <- composite (ms-fluent/Tab + digit)")

    # ⚠️ Guarded so a re-run never clobbers a hand-tuned mark: once committed,
    # the PNG is the source of truth (the same rule every other app here follows).
    if (out / "wt.png").exists():
        print("  wt.png  <- committed program mark (left as-is)")
    else:
        _draw_prompt_mark(out / "wt.png")
        print("  wt.png  <- custom (drawn: `>_` prompt in a rounded frame)")

    print(f"Wrote {len(MS_ICONS)} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
