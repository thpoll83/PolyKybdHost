#!/usr/bin/env python3
"""Fetch + render the Windows Notepad shortcut icons (reproducible source step).

Style route: **all shortcut icons come from Microsoft Fluent UI System Icons
(MIT)** — the house style across every PolyKybd app overlay, and license-clean
against the GPL-3.0-or-later host. Windows Notepad's own product icon is
Microsoft trademark art, so the ESC **program mark is drawn here** instead: a
lined page with a folded corner.

⚠️ Notepad is closed source, so unlike Windows Terminal there is no `defaults.json`
to read. Every binding in `bindings.yaml` is one that TWO independent references
agree on; the ones only one reference claims are listed in SOURCES.md as
unverified rather than guessed at.

Where an action exists in Notepad++ too, the SAME Fluent glyph is used, so the
two editors' overlays read alike.

    pip install cairosvg
    python polyhost/res/overlay_sources/notepad/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RENDER_PX = 96

# action filename -> Microsoft Fluent System Icon folder (all MIT).
# Probed against raw.githubusercontent.com before use -- there is no "Save As"
# folder, no "Calendar Ltr", no "Text Bullet List Ltr".
MS_ICONS = {
    # file  (same glyphs as the notepadpp overlay, deliberately)
    "new":        "Document Add",
    "open":       "Folder Open",
    "save":       "Save",
    "saveas":     "Save Edit",
    "print":      "Print",
    "closetab":   "Document Dismiss",
    "newwindow":  "Window New",
    "reopentab":  "Arrow Hook Up Left",
    "nexttab":    "Arrow Right",
    "prevtab":    "Arrow Left",
    # edit
    "undo":       "Arrow Undo",
    "redo":       "Arrow Redo",
    "cut":        "Cut",
    "copy":       "Copy",
    "paste":      "Clipboard Paste",
    "selectall":  "Select All On",
    "datetime":   "Calendar Clock",
    # search
    "find":       "Search",
    "findnext":   "Chevron Right",
    "findprev":   "Chevron Left",
    "replace":    "Arrow Swap",
    "goto":       "Text Position Line",
    # view / navigation
    "zoomin":     "Zoom In",
    "zoomout":    "Zoom Out",
    "zoomreset":  "Zoom Fit",
    "doctop":     "Arrow Upload",
    "docend":     "Arrow Download",
    "wordleft":   "Arrow Previous",
    "wordright":  "Arrow Next",
}



def _draw_notepad_mark(path: Path) -> None:
    """Program mark: a lined page with a folded corner.

    Drawn rather than downloaded because Notepad's own icon is Microsoft
    trademark art. White on transparent, so the binding renders it with
    `mode: alpha` -- the alpha IS the shape.
    """
    ss = 4
    u = 256 * ss
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    w = int(u * 0.05)
    l, r, t, b = u * 0.20, u * 0.80, u * 0.10, u * 0.90
    fold = u * 0.20                       # size of the dog-ear
    # page outline with the top-right corner folded away
    d.line([(l, t), (r - fold, t), (r, t + fold), (r, b), (l, b), (l, t)],
           fill=white, width=w, joint="curve")
    d.line([(r - fold, t), (r - fold, t + fold), (r, t + fold)],
           fill=white, width=w, joint="curve")
    # text rules
    for i, y in enumerate((0.46, 0.60, 0.74)):
        end = r - u * (0.10 if i < 2 else 0.24)
        d.line([(l + u * 0.10, u * y), (end, u * y)], fill=white, width=int(u * 0.042))
    img.resize((256, 256), Image.LANCZOS).save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)

    icon_fetch.fluent(MS_ICONS, out)

    # ⚠️ Guarded so a re-run never clobbers a hand-tuned mark: once committed,
    # the PNG is the source of truth (the rule every other app here follows).
    if (out / "notepad.png").exists():
        print("  notepad.png  <- committed program mark (left as-is)")
    else:
        _draw_notepad_mark(out / "notepad.png")
        print("  notepad.png  <- custom (drawn: lined page with a folded corner)")

    print(f"Wrote {len(MS_ICONS)} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
