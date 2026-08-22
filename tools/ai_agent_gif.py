#!/usr/bin/env python3
"""Animate the agent ping-pong on the real split72: badge -> tap -> Q&A -> back to typing.

A fictional but plausible session, taken from this project's own workflow: an
upstream merge hits a conflict, then the HIL rig goes red. The point of the
animation is the SHAPE of the interaction, so it shows the things a still can't:

  * the board is untouched while you type — only a corner badge appears,
  * the question STREAMS in word by word, the way the model produces it,
  * answering is a keypress, not a window,
  * and the board goes straight back to being a keyboard.

Frames are rendered through the same KLE geometry and the same CapPainter as
tools/ai_agent_demo.py, so the animation and the measured HID cost describe the
same pixels.

Usage:
    python tools/ai_agent_gif.py                    # -> tools/out/ai_agent_flow.gif
    python tools/ai_agent_gif.py --out docs/sketches/ai_agent_flow.gif --width 1200
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
HOME = os.path.dirname(HOST_REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, HOST_REPO)

from kle_render import KeyContent, KleRenderer, Theme                      # noqa: E402
from ai_layer_demo import CapPainter, parse_layout_matrix, parse_layer_keycodes  # noqa: E402
from ai_agent_demo import legend_for                                       # noqa: E402

from ai_agent_scenario import (ROUNDS, ROW_QUESTION, OPTION_ROWS,   # noqa: E402
                               AGENT_KEY, CANCEL_KEY)


def build(matrix_kc, painter):
    """Return (typing, prompt) scene builders bound to this keymap."""
    def render(spec):
        out = {}
        for mp, item in spec.items():
            if item is None:
                out[mp] = KeyContent(dim=True)
                continue
            label, frame, badge, invert = item
            out[mp] = KeyContent(image=painter.paint(label, None, invert=invert,
                                                     frame=frame, badge=badge))
        return out

    def typing(badge=None, pressed=None):
        """The ordinary keyboard. `badge` puts a count on the agent key."""
        spec = {}
        for mp, kc in matrix_kc.items():
            base = legend_for(kc)
            if kc == AGENT_KEY:
                spec[mp] = ("AI", None, badge, kc == pressed)
            elif base is not None:
                spec[mp] = (base, None, None, kc == pressed)
            else:
                spec[mp] = None
        return render(spec)

    def lay_out(text, keys):
        """One word per key, wrapping onto the next key; long words shrink to fit."""
        return dict(zip(keys, text.split()))

    def prompt(q_words=None, who=None, options=(), pressed=None):
        """The board as a dialog.

        `q_words` limits how much of the question has arrived (streaming);
        `options` are whole sentences, each laid across its own row.
        """
        cells, badges = {}, {}
        if q_words is not None:
            for key, word in zip(ROW_QUESTION, q_words.split()):
                cells[key] = word
        pressed_keys = set()
        for i, text in enumerate(options):
            row = OPTION_ROWS[i]
            placed = lay_out(text, row)
            cells.update(placed)
            if row:
                badges[row[0]] = str(i + 1)
            if pressed == i:
                pressed_keys |= set(placed)          # the whole row IS the button
        spec = {}
        for mp, kc in matrix_kc.items():
            if kc in cells:
                spec[mp] = (cells[kc], None, badges.get(kc), kc in pressed_keys)
            elif kc == CANCEL_KEY and options:
                spec[mp] = ("esc", None, None, False)
            elif kc == AGENT_KEY and who:
                spec[mp] = (who, None, None, False)
            else:
                spec[mp] = None
        return render(spec)

    return typing, prompt


def storyboard(typing, prompt):
    """(frame, duration_ms) pairs — the whole session."""
    seq = []
    def add(frame, ms, label):
        seq.append((frame, ms, label))

    add(typing(), 1500, "typing")                                   # you are typing
    for _ in range(2):                                    # the badge blinks for attention
        add(typing(badge="1"), 320, "blink-on")
        add(typing(), 260, "blink-off")
    add(typing(badge="1"), 1100, "badge-rests")                          # ...then just sits there

    for i, rnd in enumerate(ROUNDS):
        add(typing(badge=str(len(ROUNDS) - i), pressed=AGENT_KEY), 220, f"r{i}-tap")
        add(prompt("", who=rnd["who"]), 140, f"r{i}-clear")
        words = rnd["q"].split()
        # The question streams in a few words at a time — the model's own cadence.
        for n in range(3, len(words) + 1, 3):
            add(prompt(" ".join(words[:n]), who=rnd["who"]), 300, f"r{i}-q{n}")
        add(prompt(rnd["q"], who=rnd["who"]), 500, f"r{i}-qfull")
        # then the options land, one row at a time
        for n in range(1, len(rnd["options"]) + 1):
            add(prompt(rnd["q"], who=rnd["who"], options=rnd["options"][:n]),
                420, f"r{i}-opt{n}")
        add(prompt(rnd["q"], who=rnd["who"], options=rnd["options"]), 2600, f"r{i}-read")
        add(prompt(rnd["q"], who=rnd["who"], options=rnd["options"],
                   pressed=rnd["press"]), 420, f"r{i}-answer")
        add(prompt("", who=rnd["who"]), 160, f"r{i}-done")
        if i == 0:
            add(typing(), 900, "back-to-typing")          # between rounds
            add(typing(badge="1"), 320, "blink2-on")      # ...the rig comes back
            add(typing(), 260, "blink2-off")

    add(typing(), 2200, "end")                                   # and back to work
    return seq


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--qmk', default=os.path.join(HOME, 'qmk_firmware'))
    ap.add_argument('--kle', default=os.path.join(HOST_REPO, 'polyhost', 'res',
                                                  'polykybd-split72.json'))
    ap.add_argument('--out', default=os.path.join(HERE, 'out', 'ai_agent_flow.gif'))
    ap.add_argument('--unit', type=int, default=170)
    ap.add_argument('--width', type=int, default=1200, help='final GIF width in px')
    ap.add_argument('--gap', type=int, default=28)
    ap.add_argument('--margin', type=int, default=12)
    ap.add_argument('--exclude', default='3,7;8,0')
    ap.add_argument('--colors', type=int, default=96, help='GIF palette size')
    ap.add_argument('--dump-frames', help='also write every frame as a labelled PNG')
    args = ap.parse_args()

    pk = next((p for p in (os.path.join(args.qmk, 'keyboards', 'polykybd'),
                           os.path.join(args.qmk, 'keyboards', 'handwired', 'polykybd'))
               if os.path.isdir(p)), None)
    if pk is None:
        raise SystemExit(f"no keyboards/polykybd under {args.qmk} — pass --qmk")

    matrices = parse_layout_matrix(os.path.join(pk, 'split72', 'keyboard.json'))
    keycodes = parse_layer_keycodes(
        os.path.join(pk, 'split72', 'keymaps', 'default', 'keymap.c'), "_L0")
    matrix_kc = dict(zip(matrices, keycodes))

    theme = Theme()
    renderer = KleRenderer(json.load(open(args.kle, encoding='utf-8')),
                           unit=args.unit, theme=theme, margin=args.margin,
                           exclude={m.strip() for m in args.exclude.split(';') if m.strip()})
    renderer.compact_halves(lambda mp: 'L' if int(mp.split(',')[0]) < 5 else 'R',
                            gap_px=args.gap)

    typing, prompt = build(matrix_kc, CapPainter(theme))
    seq = storyboard(typing, prompt)
    frames = [f for f, _, _ in seq]
    durations = [d for _, d, _ in seq]
    scale = args.width / renderer.cw
    if args.dump_frames:
        os.makedirs(args.dump_frames, exist_ok=True)
        for i, (f, _, label) in enumerate(seq):
            renderer.render_frame(f).save(
                os.path.join(args.dump_frames, f"{i:02d}_{label}.png"))
        print(f"  dumped {len(seq)} labelled frames to {args.dump_frames}")
    out = renderer.save_gif(frames, args.out, durations, loop=0, scale=scale,
                            colors=args.colors, palette_from_all=True)
    kb = os.path.getsize(out) / 1024
    print(f"  wrote {out}  ({len(frames)} frames, {kb:.0f} KB, "
          f"{sum(durations)/1000:.1f}s, {int(renderer.cw*scale)}px wide)")


if __name__ == '__main__':
    main()
