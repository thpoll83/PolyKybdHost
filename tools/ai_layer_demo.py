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
FONT_TEXT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# A row of keycaps reads as ONE text strip. Continuous prose is broken at LETTER
# boundaries, not word boundaries: a real agent question is far too long to spend a
# whole 72x40 panel on the word "in", and word-per-key wastes most of the row. A
# glyph is never cut in half -- one that would straddle a cap edge is pushed to the
# next cap -- so the split lands in the physical gutter between two caps, which is
# where the eye already expects a break.
#
# Fill order is LINE-MAJOR: line 0 runs across every cap of the row, then line 1.
# The row is a paragraph, exactly as if it were one wide display. See FLOW_ORDERS.
FLOW_PAD = 2          # left/right margin inside one cap
FLOW_ORDERS = ("line", "cap")
FLOW_PRESETS = {      # lines per cap -> (px em, ink top per line, ink top when solo)
    2: (14, (3, 21), 13),
    3: (10, (2, 15, 28), 15),
}

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

    # ---------------------------------------------------------------- text flow

    def flow(self, text: str, n_keys: int, marker: str | None = None,
             lines: int = 2, order: str = "line"):
        """Lay ``text`` across ``n_keys`` caps; return ``(buffers, overflow)``.

        ``overflow`` is the tail that did not fit, so a caller can page rather than
        silently truncate.

        ⚠️ ``order`` decides the fill, and the two read very differently:

        ``"line"`` (default) runs line 0 across every cap of the row before
        starting line 1 -- the row is one paragraph, as if it were a single wide
        display. ``"cap"`` fills both lines of one cap before moving to the next,
        so each cap is a self-contained ~16-character chunk.

        Line-major wins for a reason that only shows up once the text is real: a
        12-cap row holds ~106 characters on ONE line, and most agent *options* are
        shorter than that, so they render as a single clean line with no second
        row to wonder about -- ``lines`` is a ceiling, not a quota. Cap-major uses
        both lines of its first caps on every row, however short the text, and
        leaves the rest of the row blank, so it forces the "which line next?"
        question even where nothing needed it.
        """
        if order not in FLOW_ORDERS:
            raise ValueError(f"order must be one of {FLOW_ORDERS}, got {order!r}")
        pt, bases, solo = FLOW_PRESETS[lines]
        font = ImageFont.truetype(FONT_TEXT, pt)
        indent = [FLOW_PAD] * n_keys
        if marker and n_keys:
            indent[0] = FLOW_PAD + 15

        placed, used = self._place(text, n_keys, font, indent, len(bases), order)
        # A row that needs only one line CENTRES it, so a short option reads as an
        # ordinary line of text rather than as text clinging to the top of the cap.
        rows = max((line for _, line, _, _ in placed), default=0) + 1
        ys = (solo,) if rows == 1 else bases

        bufs = [Image.new("L", (OLED_W, OLED_H), 0) for _ in range(n_keys)]
        draws = [ImageDraw.Draw(b) for b in bufs]
        if marker and n_keys:
            self._marker(draws[0], marker, ys[0])
        top = self._top(draws[0], font)
        for k, line, x, ch in placed:
            draws[k].text((x, ys[line] - top), ch, font=font, fill=255)
        return bufs, text[used:]

    @staticmethod
    def _place(text, n_keys, font, indent, n_lines, order):
        """-> (list of (cap, line, x, char), characters consumed).

        Laying out first and drawing second is what lets the caller discover how
        many lines the text actually needed before it commits to a baseline.
        """
        placed = []
        k = line = 0
        x = indent[0]
        i = 0
        while i < len(text):
            ch = text[i]
            w = font.getlength(ch)
            if x + w > OLED_W - FLOW_PAD:                  # this line of this cap is full
                if order == "line":
                    k += 1                                 # ...continue on the next CAP
                    if k >= n_keys:
                        line += 1                          # ...then wrap to the next LINE
                        k = 0
                        if line >= n_lines:
                            break
                else:
                    line += 1                              # ...continue on the next LINE
                    if line >= n_lines:
                        line = 0                           # ...then move to the next CAP
                        k += 1
                        if k >= n_keys:
                            break
                x = indent[k] if line == 0 else FLOW_PAD
                if ch == " ":                              # no leading space on a line
                    i += 1
                    continue
            placed.append((k, line, x, ch))
            x += w
            i += 1
        return placed, i

    @staticmethod
    def _top(d, font):
        """Ink-top offset, so every character sits on ONE baseline.

        Without it PIL anchors each character at its own bbox top and the line
        turns into a staircase -- 'a' riding as high as 'l'.
        """
        return d.textbbox((0, 0), "Ag", font=font)[1]

    def _marker(self, d, marker: str, base: int):
        """The option number: a knocked-out digit, so it reads as a list bullet.

        ``base`` is the ink top of the line it sits on, so it follows the text down
        when a one-line row centres itself.
        """
        top = base - 2
        d.rounded_rectangle([1, top, 13, top + 13], radius=3, fill=255)
        f = ImageFont.truetype(FONT_BOLD, 11)
        b = d.textbbox((0, 0), marker, font=f)
        d.text((7 - (b[2] - b[0]) / 2 - b[0], top + 7 - (b[3] - b[1]) / 2 - b[1]),
               marker, font=f, fill=0)

    def from_buffer(self, buf: Image.Image, invert: bool = False):
        """(RGB cell, 1-bit mask) for a buffer ``flow()`` produced."""
        mask = buf.point(lambda v: 255 if v >= 110 else 0).convert("1")
        fg, bgc = (self.bg, self.on) if invert else (self.on, self.bg)
        rgb = Image.new("RGB", (OLED_W, OLED_H), bgc)
        rgb.paste(Image.new("RGB", (OLED_W, OLED_H), fg), (0, 0), mask)
        return rgb, mask

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
