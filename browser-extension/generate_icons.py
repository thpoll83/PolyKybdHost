#!/usr/bin/env python3
"""Generate the extension icon set from the PolyKybd grayscale brand mark.

Reproducible: run from anywhere (paths resolve relative to this file) to
regenerate icons/icon-{16,32,48,128}.png from the app's own grayscale brand
icon (polyhost/res/icons/pgray.png) — no badge, just the resized mark.

Needs Pillow. From the repository root:
  .venv/bin/python browser-extension/generate_icons.py
"""
import pathlib

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
BRAND = HERE.parent / "polyhost" / "res" / "icons" / "pgray.png"
OUT = HERE / "icons"
SIZES = (16, 32, 48, 128)


def main():
    OUT.mkdir(exist_ok=True)
    base = Image.open(BRAND).convert("RGBA")
    for sz in SIZES:
        img = base.resize((sz, sz), Image.LANCZOS)
        img.save(OUT / f"icon-{sz}.png")
        print(f"wrote icons/icon-{sz}.png")


if __name__ == "__main__":
    main()
