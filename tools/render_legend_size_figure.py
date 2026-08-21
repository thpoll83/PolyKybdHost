#!/usr/bin/env python3
"""Render the docs figures for the keycap legend size (HID cmd 34) — real legends
for a real layout, either as a strip of keys or as the whole board.

    # a strip: one labelled row per size
    python3 tools/render_legend_size_figure.py \
        --lang fr-FR --keys KC_2,KC_7,KC_9,KC_0,KC_Q \
        --out ../polykybd-docs/src/assets/using/legend-sizes-french.png

    # the whole split72 board, one per size
    python3 tools/render_legend_size_figure.py --board --lang fr-FR \
        --out ../polykybd-docs/src/assets/using/legend-size-board-french.png

`--board` reuses `lang_demo`'s parsing (keyboard.json -> matrix, keymap.c -> the
base layer, keycode_helper.c -> the static legends) and `kle_render`'s real KLE
geometry, so every key is the key the firmware would draw there — including the
rotated thumbs and the two positions with no display. It drops the demo's caption
bar and adds its own size labels.

Draws through oled_preview's `render_key`, so what it shows is what the 72x40
keycap OLED shows — including the Shift and AltGr previews, which is the point of
picking a real layout: they visibly stay put while the main legend grows.

The palette and the rounded outline match the sibling figure
`src/assets/using/legend-sizes.png` so the two read as one set. Keep them matching
if either is regenerated.

⚠️ Check the cells before shipping the image — `--check` reports clipped pixels and
element overlap per cell and exits non-zero on either. A figure of a defect is
worse than no figure, and the previews sit close enough to the legend at the big
sizes that this is a real risk (see plan_main_legend's AltGr push-clear).

⚠️ `render_key` returns the panel PLUS a 2 px `OVERSHOOT` margin on every side —
(76, 44), not (72, 40) — so that ink drawn outside the panel stays visible. The
panel occupies cols/rows `OVERSHOOT .. OVERSHOOT + OLED_* - 1`; reading from 0
shifts the whole cell up-left by 2 px AND chops the panel's last two columns. That
is invisible on a glyph sitting away from the edge and obvious on one that reaches
it — fr-FR's AltGr `@` ends on column 71 and lost its right edge, reading as an
oversized glyph spilling out of the keycap. `_panel_pixels` asserts the returned
size so a change to OVERSHOOT cannot silently re-introduce the offset.

⚠️ The keycap outline is drawn in a MARGIN around the panel, never on top of it.
A glyph may legitimately ink the outermost column — fr-FR's AltGr `@` ends on
column 71 of 0..71 — so a border stroked at the cell edge paints over it, and the
glyph reads as an oversized one spilling out of the frame. That is a defect of the
figure, not of the firmware, and it is invisible in a figure whose glyphs happen to
sit away from the edge (the sibling sample-letter figure never shows it).
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gfx_font import load_all_fonts                                    # noqa: E402
import oled_preview as OP                                              # noqa: E402
from oled_preview import (Lang, Renderer, load_named_glyphs, render_key,  # noqa: E402
                          ROW, OLED_W, OLED_H)

BG, KEY_BG, INK, BORDER, LABEL = (17, 18, 22), (6, 8, 12), (168, 216, 255), (58, 62, 72), (190, 195, 205)
ROWS = [(0, "Small  (default)"), (1, "Medium"), (2, "Large")]
SCALE, PAD, GAP, LBL_H, RADIUS = 4, 26, 24, 26, 14
FRAME = 6          # margin the outline lives in, so it never overdraws panel ink


def _panel_pixels(img):
    """The 72x40 panel out of render_key's overshoot-padded image (see the note above)."""
    want = (OLED_W + 2 * OP.OVERSHOOT, OLED_H + 2 * OP.OVERSHOOT)
    if img.size != want:
        sys.exit(f"render_key returned {img.size}, expected {want} — the panel offset "
                 f"below assumes OVERSHOOT={OP.OVERSHOOT} padding on every side")
    return img.convert("L").load()


def load(fw: str):
    L = Lang(f"{fw}/lang/lang_lut.xlsx", load_named_glyphs(f"{fw}/lang/named_glyphs.h"))
    return L, Renderer(load_all_fonts(f"{fw}/base/fonts"))


def check(L, R, lang: str, keys) -> int:
    bad = 0
    for kc in keys:
        for size, name in ROWS:
            rep = {}
            render_key(L, R, lang, kc, False, False, report=rep, size=size)
            clip, ov = sum(rep["oob"].values()), rep["overlap"]
            if clip or ov:
                bad += 1
                print(f"  {lang} {kc:16s} {name:16s} clipped={clip} overlap={ov}")
    print(f"{'FAIL' if bad else 'OK'}: {len(keys) * 3} cells checked, {bad} with a defect")
    return 1 if bad else 0


def render(L, R, lang: str, keys, out: str) -> None:
    from PIL import Image, ImageDraw, ImageFont
    kw, kh = OLED_W * SCALE, OLED_H * SCALE
    cw, ch = kw + 2 * FRAME, kh + 2 * FRAME        # panel + the outline's margin
    W = PAD * 2 + len(keys) * cw + (len(keys) - 1) * GAP
    H = PAD * 2 + len(ROWS) * (LBL_H + ch + GAP) - GAP
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
    except OSError:
        font = ImageFont.load_default()
    y = PAD
    for size, label in ROWS:
        d.text((PAD, y), label, fill=LABEL, font=font)
        y += LBL_H
        x = PAD
        for kc in keys:
            src = _panel_pixels(render_key(L, R, lang, kc, False, False, size=size))
            cell = Image.new("RGB", (kw, kh), KEY_BG)
            cd = ImageDraw.Draw(cell)
            for yy in range(OLED_H):
                for xx in range(OLED_W):
                    if src[xx + OP.OVERSHOOT, yy + OP.OVERSHOOT]:
                        cd.rectangle([xx * SCALE, yy * SCALE,
                                      xx * SCALE + SCALE - 1, yy * SCALE + SCALE - 1], fill=INK)
            d.rounded_rectangle([x, y, x + cw - 1, y + ch - 1],
                                radius=RADIUS, fill=KEY_BG, outline=BORDER, width=2)
            img.paste(cell, (x + FRAME, y + FRAME))   # ink inside the margin, never under it
            x += cw + GAP
        y += ch + GAP
    img.save(out)
    print(f"wrote {out} {img.size}")


def render_static_keys(fw: str, keys, labels, out: str) -> None:
    """A row of STATIC keycaps (keycode_to_static_text legends), labelled.

    Used for the settings-layer size keys, whose whole legend is one icon: the
    figure has to show the icon itself, since no words on the keycap say what it
    does. The legends are read from the firmware's keycode_helper.c, so a wording
    or glyph change there cannot leave the figure stale.
    """
    from PIL import Image, ImageDraw, ImageFont
    sys.path.insert(0, HERE)
    import lang_demo as LD
    OP.OVERSHOOT = 0
    static_map = LD.parse_static_text_map(os.path.join(fw, "keycode_helper.c"))
    missing = [k for k in keys if k not in static_map]
    if missing:
        sys.exit(f"no static legend for {', '.join(missing)} in keycode_helper.c")
    L, R = load(fw)
    kw, kh = OLED_W * SCALE, OLED_H * SCALE
    cw, ch = kw + 2 * FRAME, kh + 2 * FRAME
    W = PAD * 2 + len(keys) * cw + (len(keys) - 1) * GAP
    H = PAD * 2 + LBL_H + ch
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
    except OSError:
        font = ImageFont.load_default()
    x = PAD
    for kc, label in zip(keys, labels):
        d.text((x + FRAME, PAD), label, fill=LABEL, font=font)
        src = LD.render_static(L, R, static_map[kc]).load()
        cell = Image.new("RGB", (kw, kh), KEY_BG)
        cd = ImageDraw.Draw(cell)
        for yy in range(OLED_H):
            for xx in range(OLED_W):
                if src[xx, yy]:
                    cd.rectangle([xx * SCALE, yy * SCALE,
                                  xx * SCALE + SCALE - 1, yy * SCALE + SCALE - 1], fill=INK)
        y = PAD + LBL_H
        d.rounded_rectangle([x, y, x + cw - 1, y + ch - 1],
                            radius=RADIUS, fill=KEY_BG, outline=BORDER, width=2)
        img.paste(cell, (x + FRAME, y + FRAME))
        x += cw + GAP
    img.save(out)
    print(f"wrote {out} {img.size}")


def render_board(fw: str, lang: str, out: str, unit: int, layer: str = None,
                 status: bool = False, oled_gap: float = 0.30,
                 shift: bool = False) -> None:
    """The whole split72 board at each size, stacked and labelled."""
    import json
    from PIL import Image, ImageDraw, ImageFont
    sys.path.insert(0, HERE)
    import lang_demo as LD
    from kle_render import Theme
    # The status OLEDs' real place and size come from the PCB, and that geometry
    # already exists — OLED_ACTIVE_U (the Eco2.User active-area rect measured off
    # poly_kybd_split72_{left,right}.kicad_pcb) plus module_rect_bounds() (the
    # plate's 27x26 mm module opening around it). Import them rather than
    # re-deriving, so this figure and fw_confirm_preview can never disagree about
    # where the panel sits. Importing the module does not run its main().
    import fw_confirm_preview as FCP

    # ⚠️ The overshoot margin is a DEBUG aid — it pads render_key's output so ink
    # drawn outside the panel stays visible. lang_demo's board path assumes a clean
    # 72x40 keycap (its _oled_buffer builds the mask at OLED_W x OLED_H), so the
    # padded image raises "images do not match". lang_demo.main() zeroes it for
    # exactly this reason; importing the module does not run main(), so do it here.
    OP.OVERSHOOT = 0

    pk = fw
    matrices = LD.parse_layout_matrix(os.path.join(pk, "split72", "keyboard.json"))
    kcs = LD.parse_base_layer_keycodes(
        os.path.join(pk, "split72", "keymaps", "default", "keymap.c"),
        LD.BASE_LAYOUTS.get((layer or "").lower(), layer) if layer else None)
    if len(matrices) != len(kcs):
        sys.exit(f"layout/keymap length mismatch: {len(matrices)} vs {len(kcs)}")
    matrix_kc = dict(zip(matrices, kcs))
    static_map = LD.parse_static_text_map(os.path.join(pk, "keycode_helper.c"))
    L, R = load(pk)
    theme = Theme()
    kle = os.path.join(os.path.dirname(HERE), "polyhost", "res", "polykybd-split72.json")
    active = dict(FCP.OLED_ACTIVE_U)
    board = LD.LangBoard(json.load(open(kle, encoding="utf-8")), unit=unit, glyphs=None,
                         bezel=True, margin=12,
                         exclude={"3,7", "8,0"},      # the two keys with no OLED
                         dither=False,
                         panels=[FCP.module_rect_bounds(active[s]) for s in ("L", "R")]
                                if status else None)
    if status:
        # The OLEDs live in the inner gap, so with them drawn the halves are spaced
        # by what the two MODULES need, not by the key gap — same pass as
        # fw_confirm_preview. compact_halves() only knows about keys, so it would
        # overlap them.
        ml, mr = (FCP.module_rect_bounds(active["L"]), FCP.module_rect_bounds(active["R"]))
        delta = (mr[0] - ml[2]) - oled_gap
        if delta > 0:
            for mp, p_ in board.km.items():
                if int(mp.split(",")[0]) >= 5:
                    p_["x"] -= delta
                    p_["rx"] -= delta   # the pivot too, so the rotated thumbs follow
            x0, y0, x1, y1 = active["R"]
            active["R"] = (x0 - delta, y0, x1 - delta, y1)
            board.panels = [FCP.module_rect_bounds(active[s]) for s in ("L", "R")]
            board._geom()
    else:
        board.compact_halves(lambda mp: "L" if int(mp.split(",")[0]) < 5 else "R", gap_px=14)

    # The 128x64 status OLED on each half. It is driven by its OWN standalone fonts
    # (_Small_ / _Mid_ / _Nano_, see gen-status-fonts.sh), NOT by the keycap `latin`
    # face, so the legend size does not touch it — which is exactly why it is worth
    # showing: the figure then says what the setting does and does not reach.
    lit = {}
    if status:
        sys.path.insert(0, os.path.join(pk, "tools"))
        import status_oled_preview as SP
        fonts = SP.load_fonts()
        rgb = (128, 255, 100, 80, 5, "Rainbow")
        name = LD.LAYOUT_NAMES.get(LD.BASE_LAYOUTS.get((layer or "").lower(), layer or "_L0"),
                                   "Qwerty")
        # The panel's on-screen size is fixed by the PCB rect, so it will not land
        # on a whole multiple of 128x64 — supersample and LANCZOS down into the real
        # box rather than magnifying a small buffer (fw_confirm_preview's PANEL_SS).
        SS = 4
        for side in ("L", "R"):
            pts = SP.build_panel(side, *fonts, 50, rgb, lang, 0, name)
            buf = Image.new("L", (SP.P_W * SS, SP.P_H * SS), 0)
            px = buf.load()
            for (x, y) in pts:
                if 0 <= x < SP.P_W and 0 <= y < SP.P_H:
                    for dy in range(SS):
                        for dx in range(SS):
                            px[x * SS + dx, y * SS + dy] = 255
            lit[side] = buf

    def draw_status(img):
        """Module bezel + active area, at the PCB position, on one rendered board."""
        d = ImageDraw.Draw(img)
        for side in ("L", "R"):
            mx0, my0, mx1, my1 = board.panel_box_px(FCP.module_rect_bounds(active[side]))
            # Same body/outline as a keycap, so the module reads as part of the board.
            d.rounded_rectangle([mx0, my0, mx1, my1], radius=max(2, (mx1 - mx0) // 18),
                                fill=theme.key_bg, outline=theme.key_outline, width=2)
            ax0, ay0, ax1, ay1 = board.panel_box_px(active[side])
            aw, ah = max(1, ax1 - ax0), max(1, ay1 - ay0)
            panel = lit[side].resize((aw, ah), Image.LANCZOS)
            on, bg = theme.oled_on, theme.oled_bg
            cell = Image.new("RGB", (aw, ah), bg)
            cell.paste(Image.new("RGB", (aw, ah), on), (0, 0), panel)
            img.paste(cell, (ax0, ay0))

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    LH, GAP_Y = 34, 10
    frames = []
    for size, _ in ROWS:
        f = board.render_frame(LD.build_frame(L, R, matrix_kc, lang, static_map, size,
                                              shift=shift))
        if status:
            draw_status(f)
        frames.append(f)
    W = max(f.width for f in frames)
    H = sum(f.height + LH + GAP_Y for f in frames) - GAP_Y
    img = Image.new("RGB", (W, H), theme.bg)
    d = ImageDraw.Draw(img)
    y = 0
    for frame, (_, label) in zip(frames, ROWS):
        d.text((14, y + 5), label + ("   \u2014 Shift held" if shift else ""),
               fill=LABEL, font=font)
        img.paste(frame, ((W - frame.width) // 2, y + LH))
        y += frame.height + LH + GAP_Y
    img.save(out)
    print(f"wrote {out} {img.size}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fw", default=os.path.join(os.path.dirname(os.path.dirname(HERE)),
                                                 "qmk_firmware", "keyboards", "polykybd"))
    ap.add_argument("--lang", default="fr-FR")
    ap.add_argument("--keys", default="KC_2,KC_7,KC_9,KC_0,KC_Q")
    ap.add_argument("--out", help="PNG to write; omit to only --check")
    ap.add_argument("--check", action="store_true", help="report clipping/overlap per cell")
    ap.add_argument("--board", action="store_true", help="render the whole split72 board per size")
    ap.add_argument("--static-keys",
                    help="render a row of static keycaps, e.g. "
                         "KC_GLYPH_SIZE_DOWN=Smaller,KC_GLYPH_SIZE_UP=Bigger")
    ap.add_argument("--unit", type=int, default=96, help="--board: pixels per key unit")
    ap.add_argument("--layer", default=None,
                    help="--board: base layout — qwerty|stag|colemak|neo|workman or _L0.._L4")
    ap.add_argument("--status", action="store_true",
                    help="--board: also draw each half's 128x64 status OLED")
    ap.add_argument("--shift", action="store_true",
                    help="--board: draw the Shift-held view (the shifted character is "
                         "the main legend, so it grows too; the previews are dropped)")
    ap.add_argument("--oled-gap", type=float, default=0.30,
                    help="--board --status: clearance between the two OLED modules, in key "
                         "units (the halves are spaced to make room for them)")
    a = ap.parse_args()
    if a.static_keys:
        if not a.out:
            sys.exit("--static-keys needs --out")
        pairs = [p.split("=", 1) for p in a.static_keys.split(",")]
        render_static_keys(a.fw, [p[0] for p in pairs],
                           [p[1] if len(p) > 1 else p[0] for p in pairs], a.out)
        return 0
    if a.board:
        if not a.out:
            sys.exit("--board needs --out")
        render_board(a.fw, a.lang, a.out, a.unit, a.layer, a.status, a.oled_gap, a.shift)
        return 0
    keys = [k if k.startswith("KC_") else f"KC_{k}" for k in a.keys.split(",")]
    unknown = [k for k in keys if k not in ROW]
    if unknown:
        sys.exit(f"unknown keycode(s): {', '.join(unknown)}")
    L, R = load(a.fw)
    if a.lang not in L.langs:
        sys.exit(f"unknown layout {a.lang!r}")
    rc = check(L, R, a.lang, keys) if (a.check or not a.out) else 0
    if a.out:
        render(L, R, a.lang, keys, a.out)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
