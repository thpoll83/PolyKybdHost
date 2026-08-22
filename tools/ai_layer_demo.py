#!/usr/bin/env python3
"""Render the proposed PolyKybd `_AI` layer onto the real split72 geometry.

This is a *sketch* for docs/ai-integration.md — nothing here talks to a device or
to a model. It exists so the layer can be argued about as a picture of keycaps
rather than as a table in a document.

Data flow, all from real sources so the picture can't drift from the hardware:

  * key geometry     polyhost/res/polykybd-split72.json      (the layout editor's KLE)
  * arg -> matrix    split72/keyboard.json                   (LAYOUT_left_right_stacked)
  * arg -> keycode   split72/keymaps/default/keymap.c        ([_L0], the base layer)
  * keycode -> action docs/sketches/ai-layer.yaml            (the proposal itself)

Two stills are written: the resting layer, and one mid-run with a verb key
inverted (the press feedback the firmware already does), a spinner on it and the
status row filled in.

Usage:
    python tools/ai_layer_demo.py                     # -> tools/out/ai_layer*.png
    python tools/ai_layer_demo.py --out-dir /tmp/ai --unit 96
    python tools/ai_layer_demo.py --qmk /path/to/qmk_firmware
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

import yaml
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
HOME = os.path.dirname(HOST_REPO)
sys.path.insert(0, HERE)

from kle_render import KeyContent, KleRenderer, Theme  # noqa: E402

LAYOUT_NAME = "LAYOUT_left_right_stacked"
BASE_LAYER = "_L0"
OLED_W, OLED_H = 72, 40
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Status readouts shown in the "running" still. Sketch values, not measurements.
RUNNING_VALUES = {"KC_6": "1.2k", "KC_7": "310", "KC_8": "91%", "KC_9": "480", "KC_0": "$0.07"}
SPINNER = "|/-\\"


def strip_c_comments(s: str) -> str:
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'//[^\n]*', '', s)


def split_args(inner: str) -> list[str]:
    args, depth, cur = [], 0, ''
    for ch in inner:
        if ch == '(':
            depth += 1; cur += ch
        elif ch == ')':
            depth -= 1; cur += ch
        elif ch == ',' and depth == 0:
            args.append(cur.strip()); cur = ''
        else:
            cur += ch
    if cur.strip():
        args.append(cur.strip())
    return args


def parse_layout_matrix(keyboard_json: str) -> list[str]:
    """arg index -> 'row,col', straight from keyboard.json."""
    d = json.load(open(keyboard_json, encoding='utf-8'))
    return [f"{k['matrix'][0]},{k['matrix'][1]}"
            for k in d['layouts'][LAYOUT_NAME]['layout']]


def parse_layer_keycodes(keymap_c: str, layer: str) -> list[str]:
    """arg index -> keycode token for one layer of the keymap."""
    text = strip_c_comments(open(keymap_c, encoding='utf-8').read())
    try:
        i = text.index(f'[{layer}]')
        k = text.index('(', text.index(LAYOUT_NAME, i))
    except ValueError as exc:
        raise SystemExit(f"could not locate [{layer}] / {LAYOUT_NAME} in {keymap_c}") from exc
    depth, end = 0, None
    for m in range(k, len(text)):
        if text[m] == '(':
            depth += 1
        elif text[m] == ')':
            depth -= 1
            if depth == 0:
                end = m
                break
    if end is None:
        raise SystemExit(f"unbalanced {LAYOUT_NAME} parentheses in {keymap_c}")
    return split_args(text[k + 1:end])


def font_covers(path: str, text: str) -> bool:
    """True when every non-space char of ``text`` is in the font's cmap.

    A missing glyph renders as a tofu box, which in a *sketch* reads as a design
    choice rather than a missing font — so drop the glyph instead of drawing it.
    """
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return True
    try:
        cmap = set()
        for t in TTFont(path, fontNumber=0)['cmap'].tables:
            cmap |= set(t.cmap.keys())
    except Exception:
        return True
    return all(ord(c) in cmap for c in text if not c.isspace())


class CapPainter:
    """Draws one 72x40 keycap panel the way the OLED would show it."""

    def __init__(self, theme: Theme):
        self.on, self.bg = theme.oled_on, theme.oled_bg
        self.f_big = ImageFont.truetype(FONT_BOLD, 17)
        self.f_line = ImageFont.truetype(FONT_BOLD, 14)
        self.f_glyph = ImageFont.truetype(FONT_BOLD, 15)

    def _fit(self, d, text, font, max_w=OLED_W - 4):
        """Step the size down until the string fits the 72 px cell."""
        size = font.size
        while size > 8:
            f = ImageFont.truetype(FONT_BOLD, size)
            b = d.textbbox((0, 0), text, font=f)
            if b[2] - b[0] <= max_w:
                return f
            size -= 1
        return ImageFont.truetype(FONT_BOLD, 8)

    def _centre(self, d, y, text, font):
        """Draw ``text`` horizontally centred with its INK TOP at ``y``.

        Both bbox offsets have to come off: dropping the y one lets a line with
        no ascender sit lower than one with, and the bottom line then clips off
        the 40 px panel — which reads as a layout problem rather than a bug.
        """
        font = self._fit(d, text, font)
        b = d.textbbox((0, 0), text, font=font)
        d.text(((OLED_W - (b[2] - b[0])) / 2 - b[0], y - b[1]), text, font=font, fill=255)

    def paint(self, label: str, glyph: str | None = None, invert: bool = False,
              frame: str | None = None, badge: str | None = None) -> Image.Image:
        return self.paint_with_mask(label, glyph, invert, frame, badge)[0]

    def paint_with_mask(self, label: str, glyph: str | None = None,
                        invert: bool = False, frame: str | None = None,
                        badge: str | None = None):
        """Return (RGB cell for the picture, 1-bit mask for the cost model).

        Both come from the SAME buffer, so a mockup can never disagree with the
        report count measured from it.
        """
        buf = Image.new('L', (OLED_W, OLED_H), 0)
        d = ImageDraw.Draw(buf)
        lines = label.split('\n')
        if len(lines) > 1:                      # two captions, no room for a glyph
            self._centre(d, 5, lines[0], self.f_line)
            self._centre(d, 23, lines[1], self.f_line)
        elif glyph:
            self._centre(d, 4, glyph, self.f_glyph)
            self._centre(d, 23, lines[0], self.f_line)
        else:
            self._centre(d, 13, lines[0], self.f_big)
        if badge:
            # A secondary mark goes BOTTOM-right: render_key() draws the shift
            # preview in the upper right, so a top-anchored badge lands on it.
            fb = ImageFont.truetype(FONT_BOLD, 13)
            b = d.textbbox((0, 0), badge, font=fb)
            d.text((OLED_W - (b[2] - b[0]) - 2 - b[0], OLED_H - (b[3] - b[1]) - 2 - b[1]),
                   badge, font=fb, fill=255)
        if frame == 'cap':                       # the firmware's selected-tab chrome
            d.rectangle([2, 0, OLED_W - 3, 0], fill=255)
            d.rectangle([1, 1, OLED_W - 2, 1], fill=255)
            d.rectangle([0, 2, 2, OLED_H - 1], fill=255)
            d.rectangle([OLED_W - 3, 2, OLED_W - 1, OLED_H - 1], fill=255)
        mask = buf.point(lambda v: 255 if v >= 110 else 0).convert('1')
        fg, bgc = (self.bg, self.on) if invert else (self.on, self.bg)
        rgb = Image.new('RGB', (OLED_W, OLED_H), bgc)
        rgb.paste(Image.new('RGB', (OLED_W, OLED_H), fg), (0, 0), mask)
        return rgb, mask


def build_state(matrix_kc, actions, painter, *, pressed=None, values=None, spin=None):
    """{matrix_pos: KeyContent} for one frame."""
    state = {}
    for mp, kc in matrix_kc.items():
        act = actions.get(kc)
        if not act:
            state[mp] = KeyContent(dim=True)
            continue
        label, glyph = act.get('label', ''), act.get('glyph')
        if values and kc in values:
            label = f"{label.split(chr(10))[0]}\n{values[kc]}"
            glyph = None
        if pressed is not None and kc == pressed:
            label, glyph = (spin or label), None
        state[mp] = KeyContent(image=painter.paint(label, glyph, invert=(kc == pressed)))
    return state


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--qmk', default=os.path.join(HOME, 'qmk_firmware'))
    ap.add_argument('--kle', default=os.path.join(HOST_REPO, 'polyhost', 'res',
                                                  'polykybd-split72.json'))
    ap.add_argument('--layer', default=os.path.join(HOST_REPO, 'docs', 'sketches',
                                                    'ai-layer.yaml'))
    ap.add_argument('--out-dir', default=os.path.join(HERE, 'out'))
    ap.add_argument('--unit', type=int, default=170, help='pixels per key unit')
    ap.add_argument('--scale', type=float, default=0.5,
                    help='final downscale. The renderer resizes each 72x40 panel to the '
                         'key rect with NEAREST, so at a small --unit it DECIMATES the '
                         'panel (72->68 px) and drops glyph rows -- which reads as clipped '
                         'text, not as a resample. Render oversized, then LANCZOS down.')
    ap.add_argument('--gap', type=int, default=28, help='px between the halves')
    ap.add_argument('--margin', type=int, default=12)
    ap.add_argument('--press', default='KC_S', help='key shown mid-run in the second still')
    ap.add_argument('--exclude', default='3,7;8,0',
                    help='matrix positions with no OLED (the two rotary encoders)')
    ap.add_argument('--no-bezel', action='store_true')
    args = ap.parse_args()

    # keyboards/polykybd moved out of handwired/ — accept either checkout.
    pk = next((p for p in (os.path.join(args.qmk, 'keyboards', 'polykybd'),
                           os.path.join(args.qmk, 'keyboards', 'handwired', 'polykybd'))
               if os.path.isdir(p)), None)
    if pk is None:
        raise SystemExit(f"no keyboards/polykybd under {args.qmk} — pass --qmk")

    matrices = parse_layout_matrix(os.path.join(pk, 'split72', 'keyboard.json'))
    keycodes = parse_layer_keycodes(
        os.path.join(pk, 'split72', 'keymaps', 'default', 'keymap.c'), BASE_LAYER)
    if len(matrices) != len(keycodes):
        raise SystemExit(f"layout/keymap length mismatch: {len(matrices)} vs {len(keycodes)}")
    matrix_kc = dict(zip(matrices, keycodes))

    spec = yaml.safe_load(open(args.layer, encoding='utf-8'))
    actions = spec['keys']
    unplaced = [kc for kc in actions if kc not in set(keycodes)]
    if unplaced:
        raise SystemExit(f"ai-layer.yaml names keys that are not on {BASE_LAYER}: {unplaced}")
    for kc, act in actions.items():             # drop glyphs the sketch font lacks
        g = act.get('glyph')
        if g and not font_covers(FONT_BOLD, g):
            act['glyph'] = None

    theme = Theme()
    painter = CapPainter(theme)
    renderer = KleRenderer(json.load(open(args.kle, encoding='utf-8')),
                           unit=args.unit, theme=theme, bezel=not args.no_bezel,
                           margin=args.margin,
                           exclude={m.strip() for m in args.exclude.split(';') if m.strip()})
    renderer.compact_halves(lambda mp: 'L' if int(mp.split(',')[0]) < 5 else 'R',
                            gap_px=args.gap)

    os.makedirs(args.out_dir, exist_ok=True)
    shots = {
        'ai_layer.png': build_state(matrix_kc, actions, painter),
        'ai_layer_running.png': build_state(matrix_kc, actions, painter,
                                            pressed=args.press, values=RUNNING_VALUES,
                                            spin=SPINNER[1]),
    }
    for name, state in shots.items():
        path = os.path.join(args.out_dir, name)
        img = renderer.render_frame(state)
        if args.scale != 1.0:
            img = img.resize((int(img.width * args.scale), int(img.height * args.scale)),
                             Image.LANCZOS)
        img.save(path)
        print(f"  wrote {path}  ({img.width}x{img.height})")
    print(f"  {len(actions)} keys placed, {len(keycodes) - len(actions)} left dim")


if __name__ == '__main__':
    main()
