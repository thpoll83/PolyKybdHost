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
from ai_agent_demo import legend_for, AGENT_KEY                            # noqa: E402

# The session. Each round: the words that stream onto the number row, the answer
# keys, and which answer the user presses.
ROUNDS = [
    {"q": ["merge", "conflict", "in", "split_", "sync.c"],
     "who": "fw\nasks",
     "answers": [("KC_A", "OURS"), ("KC_S", "THEIRS"), ("KC_D", "SHOW")],
     "press": "KC_S"},
    {"q": ["HIL", "test", "failed", "on", "split72"],
     "who": "rig\nasks",
     "answers": [("KC_A", "RERUN"), ("KC_S", "LOGS"), ("KC_D", "STOP")],
     "press": "KC_A"},
]
QUESTION_KEYS = ["KC_1", "KC_2", "KC_3", "KC_4", "KC_5"]
CANCEL_KEY = "KC_ESC"


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

    def prompt(words, who=None, answers=(), pressed=None):
        """The board as a dialog: `words` of the question so far, then answers."""
        answer_map = dict(answers)
        spec = {}
        for mp, kc in matrix_kc.items():
            if kc in QUESTION_KEYS and QUESTION_KEYS.index(kc) < len(words):
                spec[mp] = (words[QUESTION_KEYS.index(kc)], None, None, False)
            elif kc in answer_map:
                spec[mp] = (answer_map[kc], "cap", None, kc == pressed)
            elif kc == CANCEL_KEY and answers:
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
        add(typing(badge=str(len(ROUNDS) - i), pressed=AGENT_KEY), 220, f"r{i}-tap")   # you tap it
        add(prompt([], who=rnd["who"]), 140, f"r{i}-clear")                              # board clears
        for n in range(1, len(rnd["q"]) + 1):                             # question streams
            add(prompt(rnd["q"][:n], who=rnd["who"]), 250, f"r{i}-stream{n}")
        add(prompt(rnd["q"], who=rnd["who"], answers=rnd["answers"]), 1500, f"r{i}-read")   # read it
        add(prompt(rnd["q"], who=rnd["who"], answers=rnd["answers"],
                   pressed=rnd["press"]), 260, f"r{i}-answer")                            # answer
        add(prompt([], who=rnd["who"]), 160, f"r{i}-done")                              # tear down
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
