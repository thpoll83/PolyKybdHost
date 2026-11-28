"""A picture of both halves with the overlay image each key would show
(docs/mcp-server-plan.md, version 2: `preview_overlay`). Qt-free.

The host cannot draw the legends: the keyboard's Latin faces are compiled into the
firmware and the legend of each language is the firmware's table. So a key shows
its image in white and, where the legend stays, the keycode name in grey with the
3 px gap the firmware cuts around the image's ink. A key with no image shows only
its keycode name. Layer 0, split72 key positions (res/key_positions.yaml).
"""
from __future__ import annotations

import io
import os

import numpy as np

from polyhost.device.keys import KeyCode, Modifier
from polyhost.res.overlay_layout import (CH, COMBO_CH, EXTRA_CH, GUI_CH, PRIMARY_CH, SLOT_H,
                                         SLOT_W, _has_cell, cell_for)

MATRIX_COLUMNS = 8
GAP = 4
HALF_GAP = 24
SCALE = 2
COURTYARD = 3              # KDISP_CY_DEFAULT in the firmware
_TIERS = ((".combo.mods.png", COMBO_CH), (".extra.mods.png", EXTRA_CH),
          (".gui.mods.png", GUI_CH), (".mods.png", PRIMARY_CH))


def entry_key(app, mapping):
    """The raw mapping key (a comma-separated name list) that names `app`, or None."""
    from polyhost.handler.common import mapping_key
    by_name = {}
    for raw in mapping:
        for name in str(raw).split(","):
            by_name.setdefault(name.strip(), raw)
    name = mapping_key(app, by_name)
    return by_name[name] if name is not None else None


def _channel_for(path, mod):
    name = os.path.basename(str(path))
    for suffix, chans in _TIERS:
        if name.endswith(suffix):
            return CH[chans[mod]] if mod in chans else None
    return None


def key_images(files, mod: Modifier) -> dict[int, tuple[np.ndarray, bool]]:
    """{keycode: (40x72 bool mask, legend kept)} for modifier `mod`; the last file
    that draws a key wins, as in the overlay send. `.keys.png` files are skipped
    (physical_key_images)."""
    from PIL import Image
    from polyhost.device.im_converter import NO_LEGEND_CHUNK, parse_no_legend
    out = {}
    for path in files:
        channel = _channel_for(path, mod)
        if channel is None:
            continue
        try:
            with Image.open(str(path)) as im:
                im.load()
                no_legend = parse_no_legend(im.info.get(NO_LEGEND_CHUNK))
                arr = np.asarray(im.convert("RGBA"), dtype=np.uint8)[..., channel]
        except OSError:
            continue
        for kc in KeyCode:
            if not _has_cell(kc):
                continue
            row, col = cell_for(kc)
            cell = arr[row * SLOT_H:(row + 1) * SLOT_H, col * SLOT_W:(col + 1) * SLOT_W] > 127
            if cell.any():
                out[kc.value] = (cell, (mod.value, kc.value) not in no_legend)
    return out


def physical_key_images(files) -> dict[int, tuple[np.ndarray, bool]]:
    """{matrix index: (mask, legend kept)} from the `.keys.png` files (v40)."""
    from PIL import Image
    from polyhost.device.im_converter import NO_LEGEND_CHUNK, parse_no_legend
    from polyhost.device.key_images import KEY_OVERLAY_COUNT, is_key_image_file
    from polyhost.res.overlay_layout import GRID_X
    out = {}
    for path in files:
        if not is_key_image_file(path):
            continue
        try:
            with Image.open(str(path)) as im:
                im.load()
                no_legend = parse_no_legend(im.info.get(NO_LEGEND_CHUNK))
                arr = np.asarray(im.convert("L"), dtype=np.uint8)
        except OSError:
            continue
        for idx in range(KEY_OVERLAY_COUNT):
            row, col = divmod(idx, GRID_X)
            cell = arr[row * SLOT_H:(row + 1) * SLOT_H, col * SLOT_W:(col + 1) * SLOT_W] > 127
            if cell.any():
                out[idx] = (cell, (Modifier.NO_MOD.value, idx) not in no_legend)
    return out


def _dilate(mask, r):
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(mask, dy, axis=0), dx, axis=1)
    return out


def _short(code):
    from polyhost.services.keycode_text import keycode_tables, keycode_text
    name = keycode_text(code, empty="NO")
    if "(" not in name:
        shortest = None
        for n, v in keycode_tables()[0].items():
            if v == code and n.strip("_X") and (shortest is None or len(n) < len(shortest)):
                shortest = n
        name = shortest or name
    return name[3:] if name.startswith("KC_") else name


def render_board(files, buffer, mod: Modifier = Modifier.NO_MOD) -> bytes:
    """PNG bytes: both halves, each key's image for `mod` from `files`, layer 0
    keycodes from the keymap `buffer` (layer-major, 10 x 8 per layer)."""
    from PIL import Image, ImageDraw, ImageFont
    from polyhost.services.key_names import COLUMNS_PER_HALF, load_table

    table = load_table("split72")
    images = key_images(files, mod)
    per_key = physical_key_images(files)
    rows = 5
    width = 2 * COLUMNS_PER_HALF * (SLOT_W + GAP) + HALF_GAP
    height = rows * (SLOT_H + GAP)
    canvas = np.zeros((height, width), dtype=np.uint8)
    labels = []
    for name, (row, col) in table.by_name.items():
        half, rest = name.split(":")
        x, y = (int(v) for v in rest.split("."))
        column = x - 1 if half == "L" else 2 * COLUMNS_PER_HALF - x
        left = column * (SLOT_W + GAP) + (HALF_GAP if half == "R" else 0)
        top = (y - 1) * (SLOT_H + GAP)
        code = buffer[row * MATRIX_COLUMNS + col] if row * MATRIX_COLUMNS + col < len(buffer) else 0
        cell = np.zeros((SLOT_H, SLOT_W), dtype=np.uint8)
        hit = images.get(code)
        if hit is None:
            # v40: the key's own image, where its keycode has none.
            hit = per_key.get(row * MATRIX_COLUMNS + col)
        if hit is None or hit[1]:
            labels.append((left, top, _short(code), hit[0] if hit else None))
        if hit is not None:
            cell[hit[0]] = 255
        canvas[top:top + SLOT_H, left:left + SLOT_W] = cell
    img = Image.fromarray(canvas, mode="L")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=11)
    for left, top, text, mask in labels:
        # The keycode name stands in for the legend, cut where the firmware cuts it.
        layer = Image.new("L", (SLOT_W, SLOT_H), 0)
        ImageDraw.Draw(layer).text((4, SLOT_H // 2), text[:9], fill=110, font=font, anchor="lm")
        lab = np.asarray(layer, dtype=np.uint8).copy()
        if mask is not None:
            lab[_dilate(mask, COURTYARD)] = 0
        region = np.asarray(img, dtype=np.uint8)[top:top + SLOT_H, left:left + SLOT_W]
        img.paste(Image.fromarray(np.maximum(region, lab), mode="L"), (left, top))
    for name, (row, col) in table.by_name.items():
        half, rest = name.split(":")
        x, y = (int(v) for v in rest.split("."))
        column = x - 1 if half == "L" else 2 * COLUMNS_PER_HALF - x
        left = column * (SLOT_W + GAP) + (HALF_GAP if half == "R" else 0)
        top = (y - 1) * (SLOT_H + GAP)
        draw.rectangle([left - 1, top - 1, left + SLOT_W, top + SLOT_H], outline=60)
    img = img.resize((width * SCALE, height * SCALE), Image.NEAREST)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
