#!/usr/bin/env python3
"""Every key of an overlay set as the keycap OLED shows it: lit pixels white on black.

Reads the generated PNGs (not the source icons), so the sheet shows what the
keyboard receives. One cell per binding that applies to the platform, labelled
"Mods+Key: label", plus the ESC program mark. The key count printed and drawn
comes from the spec, so a caption written from it is right.

With --check-1to1 it also checks that each cell is the binding's icon placed
1:1, and lists every cell that differs (exit status 1). Use it for sets whose
icons are drawn at their exact key area (the game sets: `fetch_icons.py` draws
them flat and the generator must not rescale them). App sets let the generator
scale each icon into its `region`, so there every cell differs and the check
says nothing. A binding whose label names a shared concept is drawn by the
shared renderer and is listed too (see SKILL.md, "A label that NAMES a
concept").

    .venv/bin/python .claude/skills/generate-app-overlays/preview_black.py \\
        polyhost/res/overlay_sources/<app>/<spec>.yaml --out /tmp/<app>.png
    # --platform macos | linux    the macOS or Linux set of the spec
    # --check-1to1                list cells that are not their icon placed 1:1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_app_overlays as g  # noqa: E402
from polyhost.res.overlay_layout import (  # noqa: E402
    CH, COMBO_CH, EXTRA_CH, GUI_CH, PRIMARY_CH, SLOT_H, SLOT_W, cell_for)

LIT = (235, 240, 255)
BG = (28, 28, 28)
FILES = (("mods", PRIMARY_CH), ("combo.mods", COMBO_CH),
         ("extra.mods", EXTRA_CH), ("gui.mods", GUI_CH))


def _crop(m):
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1] if ys.size else m


def _output(spec: dict, platform: str) -> str:
    if platform == g.PLAT_MACOS and g.spec_needs_macos_set(spec):
        return g.macos_output(spec)
    if platform == g.PLAT_LINUX and g.spec_needs_linux_set(spec):
        return g.linux_output(spec)
    return spec["output"]


def cell_of(image: np.ndarray, key: str, channel: int) -> np.ndarray:
    """The 40 x 72 cell of `key` in one channel of an overlay PNG, as bool."""
    r, c = cell_for(g.resolve_key(key))
    return image[r * SLOT_H:(r + 1) * SLOT_H, c * SLOT_W:(c + 1) * SLOT_W, channel] > 0


def cells(spec_path: Path, platform: str, res: Path):
    """(output stem, [(label, 40x72 bool cell, 1:1 with its icon or None)]), ESC last."""
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    out = _output(spec, platform)
    icon_dir = spec_path.parent / spec.get("icon_dir", "icons")
    images: dict[str, np.ndarray] = {}
    result = []
    for b in spec["bindings"]:
        if not g.binding_applies(b, platform):
            continue
        mod = g.resolve_modifier(b.get("mods") or [], platform=platform)
        for suffix, table in FILES:
            if mod in table:
                name, ch = f"{out}.{suffix}.png", CH[table[mod]]
                break
        else:
            raise SystemExit(f"no overlay file for modifier {mod} ({b})")
        if name not in images:
            images[name] = np.array(Image.open(res / "overlays" / name).convert("RGBA"))
        cell = cell_of(images[name], str(b["key"]), ch)
        same = None
        icon = icon_dir / str(b.get("icon", ""))
        if b.get("icon") and icon.is_file():
            src = np.asarray(Image.open(icon).convert("RGBA").getchannel("A")) > 127
            a, s = _crop(cell), _crop(src)
            same = a.shape == s.shape and bool((a == s).all())
        mods = "+".join(m.title() for m in (b.get("mods") or []))
        key = str(b["key"])
        key = key.title() if len(key) > 1 else key
        result.append((f"{mods + '+' if mods else ''}{key}: {b.get('label', '')}", cell, same))
    primary = np.array(Image.open(res / "overlays" / f"{out}.mods.png").convert("RGBA"))
    esc = cell_of(primary, "ESC", CH["A"])
    if esc.any():
        result.append(("Esc: program mark", esc, None))
    return out, result


def sheet(title: str, items, cols: int = 6, scale: int = 3) -> Image.Image:
    """`items` [(label, 40x72 bool cell, ...)] as lit-on-black cells with labels."""
    cw, ch = 72 * scale, 40 * scale
    rows = (len(items) + cols - 1) // cols
    im = Image.new("RGB", (cols * (cw + 8) + 8, rows * (ch + 22) + 30), BG)
    d = ImageDraw.Draw(im)
    d.text((8, 8), title, fill=(220, 220, 220))
    for i, item in enumerate(items):
        label, m = item[0], item[1]
        x, y = 8 + (i % cols) * (cw + 8), 28 + (i // cols) * (ch + 22)
        d.text((x, y), label[:44], fill=(120, 220, 120))
        rgb = np.zeros((40, 72, 3), np.uint8)
        rgb[m] = LIT
        im.paste(Image.fromarray(rgb).resize((cw, ch), Image.NEAREST), (x, y + 14))
    return im


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--platform", default=g.PLAT_WINDOWS,
                    choices=[g.PLAT_WINDOWS, g.PLAT_MACOS, g.PLAT_LINUX])
    ap.add_argument("--res", type=Path, default=ROOT / "polyhost" / "res")
    ap.add_argument("--check-1to1", action="store_true",
                    help="list cells that are not their icon placed 1:1")
    a = ap.parse_args()
    out, items = cells(a.spec, a.platform, a.res)
    keys = sum(1 for item in items if item[0] != "Esc: program mark")
    sheet(f"{out} ({a.platform}): {keys} keys + ESC mark", items).save(a.out)
    print(f"{out}: {keys} keys, sheet {a.out}")
    if a.check_1to1:
        off = sorted({lbl for lbl, _m, same in items if same is False})
        print("cells not 1:1 with their icon:", off or "none")
        return 1 if off else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
