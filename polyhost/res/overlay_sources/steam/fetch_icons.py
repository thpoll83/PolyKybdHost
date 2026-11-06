#!/usr/bin/env python3
"""Fetch + render the Steam client shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) for `ms:` entries. The ESC mark is the Steam logo from Simple
Icons (CC0 artwork; nominative use, see `../brand_marks.py`).

The Big Picture keys stand in for controller buttons, so their icons are the
button names drawn as badges (LB, RT, A, ...). They are drawn here, white on
transparent, so the bindings render them with `mode: alpha`.

    pip install cairosvg
    python polyhost/res/overlay_sources/steam/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

FLUENT = {
    "find": "Search",
    "chat": "Chat Empty",
    "closechat": "Chat Dismiss",
    "quickaccess": "More Horizontal",
    "viewbutton": "Square Multiple",
    "menubutton": "Navigation",
}

# Badge name -> (text, shape). "pill" is a rounded rectangle (shoulder buttons
# and stick clicks), "ring" a circle (face buttons).
BADGES = {
    "btn_a": ("A", "ring"),
    "btn_x": ("X", "ring"),
    "btn_y": ("Y", "ring"),
    "btn_lb": ("LB", "pill"),
    "btn_rb": ("RB", "pill"),
    "btn_lt": ("LT", "pill"),
    "btn_rt": ("RT", "pill"),
    "btn_l3": ("L3", "pill"),
    "btn_r3": ("R3", "pill"),
}

# Drawn at 4x the 36x32 key area, then reduced, so the outline stays 2 px.
W, H, S = 36, 32, 4


def _badge(path: Path, text: str, shape: str) -> None:
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    stroke = 3 * S
    if shape == "ring":
        r = (H * S) // 2 - stroke // 2 - S
        cx, cy = (W * S) // 2, (H * S) // 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=white, width=stroke)
        font = ImageFont.truetype(BOLD, 20 * S)
    else:
        pad = stroke // 2 + S
        d.rounded_rectangle([pad, 4 * S, W * S - pad, H * S - 4 * S],
                            radius=8 * S, outline=white, width=stroke)
        font = ImageFont.truetype(BOLD, 15 * S)
    d.text(((W * S) / 2, (H * S) / 2), text, font=font, fill=white, anchor="mm")
    img.resize((W, H), Image.LANCZOS).save(path)


def _chat_step(base: Path, path: Path, forward: bool) -> None:
    """The Fluent chat bubble with a chevron inside: next or previous chat."""
    img = Image.open(base).convert("RGBA")
    n = img.width
    d = ImageDraw.Draw(img)
    cx, cy, h = n * 0.50, n * 0.45, n * 0.19
    dx = h * 0.9 if forward else -h * 0.9
    pts = [(cx - dx / 2, cy - h), (cx + dx / 2, cy), (cx - dx / 2, cy + h)]
    d.line(pts, fill=(0, 0, 0, 255), width=max(2, round(n * 0.085)), joint="curve")
    img.save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    _chat_step(out / "chat.png", out / "nextchat.png", forward=True)
    _chat_step(out / "chat.png", out / "prevchat.png", forward=False)
    for name, (text, shape) in BADGES.items():
        _badge(out / f"{name}.png", text, shape)
    brand_marks.ensure(out / "steam.png", "steam")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
