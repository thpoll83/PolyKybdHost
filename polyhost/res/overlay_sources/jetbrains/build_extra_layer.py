#!/usr/bin/env python3
"""Build jetbrains_template.extra.mods.png (Ctrl+Alt+Shift layer).

The jetbrains overlays were hand-drawn in GIMP (no bindings.yaml), so this builds
the third file directly — but through the generator's own cell/render helpers, so
the icon placement and 1-bit threshold match the other two files exactly.

Only the RED channel is written: in a '*.extra.mods.png' R = CTRL_ALT_SHIFT and
G/B/A are reserved for the future GUI pairs. The program-icon marker is copied
from the existing primary file's NO_MOD (alpha) channel so it is byte-identical
to the marker on every other layer — which means the host's byte-level dedup
stores it once and this whole file costs a single extra pool slot.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# polyhost/res/overlay_sources/jetbrains/<this file> -> four levels up is the repo
# root. Derived rather than hard-coded so the script runs from any checkout (it
# imports the generator from scripts/ and writes the PNG back into the tree).
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
import generate_app_overlays as G  # noqa: E402

ICONS = REPO / "polyhost/res/overlay_sources/icons"
PRIMARY = REPO / "polyhost/res/overlays/jetbrains_template.mods.png"
OUT = REPO / "polyhost/res/overlays/jetbrains_template.extra.mods.png"

# IntelliJ IDEA default keymap (Windows/Linux). Icons picked from the existing
# shared set so the file needs no new assets.
BINDINGS = [
    ("N",      "goto.png",      "Go to Symbol"),
    ("C",      "copy.png",      "Copy Reference"),
    ("J",      "selectall.png", "Select All Occurrences"),
    ("V",      "paste.png",     "Paste as Plain Text"),
    ("INSERT", "new.png",       "New Scratch File"),
]

extra = np.zeros((G.IMG_H, G.IMG_W, 4), dtype=np.uint8)
R = G.CH["R"]

# --- shortcut icons -------------------------------------------------------- #
region = G.region_box("bottom-right", (40, 36), 0)
placed = []
for key, icon, label in BINDINGS:
    kc = G.resolve_key(key)
    row, col = G.cell_for(kc)
    mask = G.render_icon(ICONS / icon, "contain", 150, None, region, "alpha")
    y0, x0 = row * G.SLOT_H, col * G.SLOT_W
    block = extra[y0:y0 + G.SLOT_H, x0:x0 + G.SLOT_W, R]
    block[mask] = 255
    placed.append((key, label, icon, (row, col), int(mask.sum())))

# --- program-icon marker on ESC, copied from the primary file --------------- #
prim = np.array(Image.open(PRIMARY).convert("RGBA"))
esc_row, esc_col = G.cell_for(G.resolve_key("ESC"))
ey, ex = esc_row * G.SLOT_H, esc_col * G.SLOT_W
marker = prim[ey:ey + G.SLOT_H, ex:ex + G.SLOT_W, 3]      # NO_MOD == alpha
extra[ey:ey + G.SLOT_H, ex:ex + G.SLOT_W, R] = marker

Image.fromarray(extra, "RGBA").save(OUT)

print(f"wrote {OUT}  ({OUT.stat().st_size} B)")
print(f"{'key':<8} {'cell':<8} {'lit':>5}  shortcut / icon")
for key, label, icon, cell, lit in placed:
    print(f"  {key:<6} {str(cell):<8} {lit:>5}  Ctrl+Alt+Shift+{key} = {label}  [{icon}]")
print(f"  {'ESC':<6} {str((esc_row, esc_col)):<8} {int((marker > 0).sum()):>5}  program marker (copied from NO_MOD)")
