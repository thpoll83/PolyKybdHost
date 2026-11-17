#!/usr/bin/env python3
"""Run tutorial scripts against the default split72 keymap, with no keyboard.

Builds the stored layers (0..8) from the firmware's keymap.c the way
scripts/export_preview_data.py reads it, gives the runner a fake keyboard on
protocol 35, and prints what every step would send: the ring or guide, the
spotlight size, the ARM conditions and the reveal. A step whose ring_error is not
None points at a key the keymap does not have.

    .venv/bin/python .claude/skills/add-host-tutorial/simulate_tutorials.py            # all
    .venv/bin/python .claude/skills/add-host-tutorial/simulate_tutorials.py accents   # some
    ... --firmware ../qmk_firmware/keyboards/polykybd

Exit status 1 when any step has a ring error.
"""
import argparse
import json
import logging
import os
import pathlib
import re
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import export_preview_data as E                                          # noqa: E402
from polyhost.gui.layout_dialog import qmk_keycode_helper as qh          # noqa: E402
from polyhost.services.tutorials import loader as L                     # noqa: E402
from polyhost.services.tutorials.runner import TutorialRun              # noqa: E402

STORED = ["_L0", "_L1", "_L2", "_L3", "_L4", "_FL", "_NL", "_UL", "_ML"]
NAMES = ["Qwerty", "Stag!", "ColDH", "Neo", "Workman", "Fn", "Numpad", "Utility", "MIDI"]
ROWS, COLS = 10, 8


def stored_buffer(pk: pathlib.Path) -> list:
    legends = json.loads((ROOT / "polyhost/res/preview/legends.json").read_text())
    custom = {int(k): v for k, v in legends["custom"].items()}
    by_name = {v: k for k, v in custom.items()}
    aliases = legends["aliases"]
    names = qh.parse_qmk_keycodes(ROOT / "polyhost/res/keycodes.h")
    tags = {f"_{t}": i for i, t in qh.parse_layers_h(pk / "layers.h").items()}
    layout = json.loads((pk / "split72/keyboard.json").read_text())[
        "layouts"][E.BOARD_LAYOUT]["layout"]
    src = re.sub(r"/\*.*?\*/|//[^\n]*", "",
                 (pk / "split72/keymaps/default/keymap.c").read_text(), flags=re.S)

    def resolve(tok):
        tok = aliases.get(tok, tok)
        if tok in ("_______", "KC_TRNS"):
            return 1
        if tok in ("KC_NO", "XXXXXXX"):
            return 0
        if tok in names:
            return names[tok]
        if tok in by_name:
            return by_name[tok]
        m = re.fullmatch(r"(MO|TO|TG|DF|TT|OSL)\((_\w+)\)", tok)
        if m and m.group(2) in tags:
            return qh.encode_layer_switch(m.group(1), tags[m.group(2)])
        return 0xFFFE              # a key with a function the host cannot name

    buf = []
    for tag in STORED:
        layer = [0] * (ROWS * COLS)
        for entry, tok in zip(layout, E._layout_args(src, tag)):
            r, c = entry["matrix"]
            layer[r * COLS + c] = resolve(tok)
        buf += layer
    return buf


class FakeKeyboard:
    protocol_version = 35
    device_settings = types.SimpleNamespace(MATRIX_ROWS=ROWS, MATRIX_COLUMNS=COLS)

    def __init__(self, buf):
        self.buf, self.log = buf, []

    def supports(self, _feature):
        return True

    def tutorial_info(self):
        return True, {}

    def tutorial_text(self, a, b):
        self.log.append(("text", a, b))
        return True, "ok"

    def tutorial_spotlight(self, keys):
        self.log.append(("spot", None if keys is None else len(keys)))
        return True, "ok"

    def tutorial_reveal(self, r, c):
        self.log.append(("reveal", r, c))
        return True, "ok"

    def tutorial_arm(self, conds):
        self.log.append(("arm", list(conds)))
        return True, "ok"

    def tutorial_poll(self):
        return True, {"flags": 0, "armed": 0, "matched": 0, "layer": 0}

    def tutorial_end(self):
        return True, "ok"

    def get_layer_names(self):
        return True, list(NAMES)

    def get_default_layer(self):
        return True, 0

    def get_dynamic_buffer(self):
        return True, list(self.buf)

    def key_attention(self, r, c, _n, _p):
        self.log.append(("ring", r, c))
        return True, "ok"

    def key_guide(self, steps, target, _n, _p):
        self.log.append(("guide", [tuple(s) for s in steps], target))
        return True, "ok"

    def key_attention_cancel(self):
        self.log.append(("cancel",))
        return True, "ok"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ids", nargs="*", help="tutorial ids (default: every shipped one)")
    ap.add_argument("--firmware", default=str(ROOT.parent / "qmk_firmware/keyboards/polykybd"))
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    found, errors = L.load_all()[:2]
    for e in errors:
        print("LOAD ERROR", e)
    buf = stored_buffer(pathlib.Path(args.firmware))
    bad = bool(errors)
    for tid in args.ids or sorted(found):
        tutorial = found[tid]
        kb = FakeKeyboard(buf)
        run = TutorialRun(tutorial, kb)
        print(f"===== {tid}")
        run.start()
        for i in range(len(tutorial.steps)):
            st = run.state()
            json.dumps(st)        # the control socket must be able to send it
            sent = [x for x in kb.log if x[0] != "text"]
            print(f" step {i + 1}: ring={st['ring']} err={st['ring_error']} {sent}")
            bad |= st["ring_error"] is not None
            kb.log.clear()
            if i + 1 < len(tutorial.steps):
                run.next()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
