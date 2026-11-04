#!/usr/bin/env python3
"""Every key a game-asset reader changes: the shipped icon beside the one read from the game.

Runs the reader's own build path (`build.build`) on a folder of real game files,
compares the built copy of each overlay PNG with the shipped one cell by cell
and channel by channel, and draws each changed cell twice, white on black as the
keycap OLED shows it: shipped on the left, from the game on the right.

    .venv/bin/python .claude/skills/evaluate-game-asset-reader/reader_compare.py \\
        polyhost/res/overlay_sources/<game>/<spec>.yaml --data <folder> --out /tmp/cmp.png
    # --variant <value>   for a reader with variants (the faction), else the first

`--data` is what the reader's folder setting would hold (the game's data folder
for Factorio, the game folder with `versions/` for Minecraft, the install folder
for StarCraft). The script prints the keys that changed; a key the spec names
but that did not change was not read (missing file or a refused picture).
"""
from __future__ import annotations

import argparse
import sys
import tempfile
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
from polyhost.services.game_assets import build  # noqa: E402
from polyhost.services.game_assets.readers import READERS  # noqa: E402

LIT = (235, 240, 255)
BG = (28, 28, 28)
FILES = (("mods", PRIMARY_CH), ("combo.mods", COMBO_CH),
         ("extra.mods", EXTRA_CH), ("gui.mods", GUI_CH))


def labels(spec: dict) -> dict:
    """{(file suffix, row, col, channel): "Mods+Key: label"} for the Windows set."""
    out = {}
    for b in spec.get("bindings", []):
        if not g.binding_applies(b, g.PLAT_WINDOWS):
            continue
        mod = g.resolve_modifier(b.get("mods") or [], platform=g.PLAT_WINDOWS)
        for suffix, table in FILES:
            if mod in table:
                r, c = cell_for(g.resolve_key(str(b["key"])))
                mods = "+".join(m.title() for m in (b.get("mods") or []))
                out[(suffix, r, c, CH[table[mod]])] = f"{mods + '+' if mods else ''}{b['key']}: {b.get('label', '')}"
                break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec", type=Path)
    ap.add_argument("--data", type=Path, required=True, help="the folder the reader reads")
    ap.add_argument("--variant", default="")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    spec = yaml.safe_load(a.spec.read_text(encoding="utf-8"))
    decl = READERS[spec["game_assets"]["reader"]]
    settings = {decl.folder: str(a.data)} if decl.folder else {}
    if decl.variant and a.variant:
        settings[decl.variant] = a.variant
    names = labels(spec)
    rows = []
    with tempfile.TemporaryDirectory() as cache:
        for suffix, _table in FILES:
            template = f"{spec['output']}.{suffix}.png"
            shipped_path = build.RES / "overlays" / template
            if not shipped_path.is_file():
                continue
            built = build.build(template, a.spec, settings.get, Path(cache), hint=str(a.data))
            if built is None:
                raise SystemExit(f"the reader found no game files in {a.data}")
            shipped = np.array(Image.open(shipped_path).convert("RGBA"))
            game = np.array(Image.open(built).convert("RGBA"))
            for r in range(shipped.shape[0] // SLOT_H):
                for c in range(shipped.shape[1] // SLOT_W):
                    for ch in range(4):
                        win = np.s_[r * SLOT_H:(r + 1) * SLOT_H, c * SLOT_W:(c + 1) * SLOT_W, ch]
                        before, after = shipped[win] > 0, game[win] > 0
                        if (before != after).any():
                            label = names.get((suffix, r, c, ch), f"{suffix} r{r} c{c} ch{ch}")
                            rows.append((label, before, after))
    if not rows:
        print("no key changed: the reader drew nothing from these files")
        return 1
    scale = 3
    cw, chh = 72 * scale, 40 * scale
    lw = 260
    im = Image.new("RGB", (lw + 2 * (cw + 8), len(rows) * (chh + 8) + 30), BG)
    d = ImageDraw.Draw(im)
    d.text((lw, 8), "shipped", fill=(220, 220, 220))
    d.text((lw + cw + 8, 8), f"from the game ({a.data.name})", fill=(255, 170, 60))
    for i, (label, before, after) in enumerate(rows):
        y = 28 + i * (chh + 8)
        d.text((4, y + chh // 2 - 6), label[:40], fill=(120, 220, 120))
        for j, m in enumerate((before, after)):
            rgb = np.zeros((40, 72, 3), np.uint8)
            rgb[m] = LIT
            im.paste(Image.fromarray(rgb).resize((cw, chh), Image.NEAREST), (lw + j * (cw + 8), y))
    im.save(a.out)
    print(f"{len(rows)} cells changed, sheet {a.out}")
    for label, _b, _a in rows:
        print("  ", label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
