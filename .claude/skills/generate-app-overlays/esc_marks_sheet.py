#!/usr/bin/env python3
"""One sheet of ESC keycaps, white on black as the OLED shows them.

Reads the ESC cell (the program mark) from committed overlay PNGs, so the sheet
shows what ships, not a model of it. Each argument is an overlay stem or a glob of
stems in polyhost/res/overlays/ (without `.mods.png`):

    .venv/bin/python .claude/skills/generate-app-overlays/esc_marks_sheet.py \\
        '*craft_template' logicpro_template_mac --out /tmp/esc.png

Prints the stems it drew and the lit-pixel count of each mark. A stem whose ESC
cell is empty is still drawn (blank), so a missing mark is visible.
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_app_overlays as g  # noqa: E402

OVERLAYS = ROOT / "polyhost" / "res" / "overlays"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def esc_cell(path: Path) -> np.ndarray:
    """The no-modifier (alpha channel) ESC cell, 40x72 bool."""
    row, col = g.cell_for(g.resolve_key("ESC"))
    rgba = np.asarray(Image.open(path).convert("RGBA"))
    return rgba[row * g.SLOT_H:(row + 1) * g.SLOT_H,
                col * g.SLOT_W:(col + 1) * g.SLOT_W, 3] > 127


def stems(patterns: list[str]) -> list[str]:
    known = sorted(p.name[:-len(".mods.png")] for p in OVERLAYS.glob("*.mods.png")
                   if not p.name.endswith((".combo.mods.png", ".extra.mods.png",
                                           ".gui.mods.png")))
    out = []
    for pat in patterns:
        hits = fnmatch.filter(known, pat)
        if not hits:
            sys.exit(f"no overlay matches {pat!r} in {OVERLAYS}")
        out += [h for h in hits if h not in out]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("patterns", nargs="+", help="overlay stems or globs")
    ap.add_argument("--out", required=True, help="PNG to write")
    ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--cols", type=int, default=4)
    args = ap.parse_args()

    names = stems(args.patterns)
    cw, ch, pad = g.SLOT_W * args.scale, g.SLOT_H * args.scale, 14
    rows = (len(names) + args.cols - 1) // args.cols
    sheet = Image.new("RGB", (pad + args.cols * (cw + pad), rows * (ch + 34) + pad),
                      (40, 40, 40))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(FONT, 14)
    except OSError:
        font = ImageFont.load_default()
    for i, name in enumerate(names):
        mask = esc_cell(OVERLAYS / f"{name}.mods.png")
        x = pad + (i % args.cols) * (cw + pad)
        y = pad + (i // args.cols) * (ch + 34)
        cell = Image.fromarray(np.where(mask, 255, 0).astype("uint8"))
        sheet.paste(cell.resize((cw, ch), Image.NEAREST).convert("RGB"), (x, y))
        draw.rectangle([x, y, x + cw - 1, y + ch - 1], outline=(120, 120, 120))
        draw.text((x, y + ch + 4), name.replace("_template", ""), fill=(230, 230, 230),
                  font=font)
        print(f"{name}: {int(mask.sum())} lit pixels")
    sheet.save(args.out)
    print(f"{len(names)} ESC cells -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
