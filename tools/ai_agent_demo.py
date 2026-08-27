#!/usr/bin/env python3
"""Mock up the multi-agent flow on the real split72, and COST IT IN HID REPORTS.

Three frames, which are the three states of the proposed agent surface:

  1. typing   — your normal keyboard. One key (KC_AGENT) carries a badge with the
                pending count. Nothing else differs: this is the whole point.
  2. overview — you tapped it. Every pending agent gets a keycap: name + state.
                (One tap goes straight to frame 3 when only one agent is waiting.)
  3. question — you tapped an agent. Its question spans the number row, the
                answers sit on the home row, everything else is blank.

The frames are rendered through the same KLE geometry the hardware uses, and the
cost of each transition is measured with the host's REAL encoder — every keycap
image is run through OverlayData, which is what poly_kybd.send_smallest_overlay()
consults, so the report counts are what the device would actually receive rather
than an estimate.

Usage:
    python tools/ai_agent_demo.py                       # -> tools/out/, prints the cost table
    python tools/ai_agent_demo.py --out-dir docs/sketches
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
HOME = os.path.dirname(HOST_REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, HOST_REPO)

from kle_render import KeyContent, KleRenderer, Theme                      # noqa: E402
from ai_layer_demo import (CapPainter, parse_layout_matrix,                # noqa: E402
                           parse_layer_keycodes, font_covers, FONT_BOLD)

from polyhost.device.device_settings import DeviceSettings                 # noqa: E402
from polyhost.device.overlay_data import OverlayData                       # noqa: E402

from ai_agent_scenario import (AGENT_POS, CANCEL_POS, WHO_POS,          # noqa: E402
                               AGENT_TILES, AGENTS, ASKING, ROUNDS,
                               prompt_cells, check_fits)

ROUND = ROUNDS[0]          # the frame the cost model measures

# Base-layer legends: enough of a map to render a believable resting keyboard.
SPECIAL = {
    "KC_ESC": "esc", "KC_TAB": "tab", "KC_LSFT": "shift", "KC_RSFT": "shift",
    "KC_LCTL": "ctrl", "KC_LALT": "alt", "KC_LWIN": "os", "KC_APP": "intl",
    "KC_SPACE": "␣", "KC_SPC": "␣", "KC_ENTER": "↵", "KC_DEL": "del",
    "KC_BSPC": "⌫", "KC_MINUS": "-", "KC_EQUAL": "=", "KC_LBRC": "[",
    "KC_RBRC": "]", "KC_BSLS": "\\", "KC_QUOTE": "'", "KC_GRAVE": "`",
    "KC_COMMA": ",", "KC_DOT": ".", "KC_SLASH": "/", "KC_SCLN": ";",
    "KC_NUBS": "\\", "KC_UP": "↑", "KC_DOWN": "↓", "KC_LEFT": "←",
    "KC_RIGHT": "→", "KC_HYPR": "AI", "KC_LANG": "lang", "MS_BTN1": "mb1",
}


def legend_for(kc: str) -> str | None:
    """Base-layer label for a keycode token, or None for a key we leave dim."""
    if kc in SPECIAL:
        return SPECIAL[kc]
    if kc.startswith("MO(") or kc.startswith("TO("):
        return "fn"
    if kc.startswith("KC_") and len(kc) == 4:          # KC_A .. KC_Z, KC_0 .. KC_9
        ch = kc[3]
        return ch.lower() if ch.isalpha() else ch
    return None


NO_ANSWER_FRAME = False


def frames(matrix_kc, painter, lines=2):
    """Build the three states as {matrix_pos: (KeyContent, 72x40 bool array|None)}.

    The array is kept beside the rendered cell so the same pixels that go into the
    picture are the ones the cost model encodes — a mockup that cannot disagree
    with its own measurement.
    """
    def cell(label, glyph=None, invert=False, frame=None):
        img = painter.paint(label, glyph, invert=invert, frame=frame)
        return img

    typing, overview, question = {}, {}, {}
    # The prompt is FLOWED prose, so each cap is a pre-rendered slice of a row
    # strip rather than a word -- see ai_agent_scenario for why.
    q_cells = prompt_cells(painter, ROUND["q"], ROUND["options"], lines=lines)
    for mp, kc in matrix_kc.items():
        base = legend_for(kc)
        # --- 1. typing: the ordinary board, plus one badge
        if mp == AGENT_POS:
            typing[mp] = ("AI", None, None, "1")      # legend + bottom-right badge
        elif base is not None:
            typing[mp] = (base, None, None, None)
        else:
            typing[mp] = None

        # --- 2. overview: one tile per pending agent, everything else blank
        if mp in AGENT_TILES:
            name, state = AGENTS[AGENT_TILES.index(mp)]
            asking = AGENT_TILES.index(mp) == ASKING
            overview[mp] = (f"{name}\n{state}", None, "cap" if asking else None, None)
        elif mp == CANCEL_POS:
            overview[mp] = ("esc", None, None, None)
        else:
            overview[mp] = None

        # --- 3. question: one option per row, flowed across its caps
        if mp in q_cells:
            question[mp] = q_cells[mp]
        elif mp == CANCEL_POS:
            question[mp] = ("esc", None, None, None)
        elif mp == WHO_POS:
            question[mp] = (ROUND["who"], None, None, None)
        else:
            question[mp] = None
    return typing, overview, question


def to_state(spec, painter):
    """{matrix_pos: spec} -> ({matrix_pos: KeyContent}, {matrix_pos: bool array})."""
    import numpy as np
    content, arrays = {}, {}
    for mp, item in spec.items():
        if item is None:
            content[mp] = KeyContent(dim=True)
            continue
        if isinstance(item, Image.Image):        # a flowed prose slice
            rgb, mask = painter.from_buffer(item)
        else:
            label, glyph, frame, badge = item
            rgb, mask = painter.paint_with_mask(label, glyph, frame=frame, badge=badge)
        content[mp] = KeyContent(image=rgb)
        arrays[mp] = np.array(mask, dtype=bool)
    return content, arrays


def cost(arrays, settings, label):
    """Report count for uploading these keycap images, via the host's own encoder."""
    rows, total = [], 0
    for mp, arr in sorted(arrays.items()):
        if not arr.any():                 # an all-black cell is never uploaded
            continue
        ov = OverlayData(settings, arr)
        n = min(ov.all_msgs, ov.compressed_msgs, ov.roi_msgs, ov.compressed_roi_msgs)
        kind = ("plain" if n == ov.all_msgs else
                "compressed" if n == ov.compressed_msgs else
                "ROI" if n == ov.roi_msgs else "ROI+RLE")
        rows.append((mp, n, kind, len(ov.compressed_bytes)))
        total += n
    return {"label": label, "images": len(rows), "reports": total, "rows": rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--qmk', default=os.path.join(HOME, 'qmk_firmware'))
    ap.add_argument('--kle', default=os.path.join(HOST_REPO, 'polyhost', 'res',
                                                  'polykybd-split72.json'))
    ap.add_argument('--out-dir', default=os.path.join(HERE, 'out'))
    ap.add_argument('--unit', type=int, default=170)
    ap.add_argument('--scale', type=float, default=0.5)
    ap.add_argument('--gap', type=int, default=28)
    ap.add_argument('--margin', type=int, default=12)
    ap.add_argument('--exclude', default='3,7;8,0')
    ap.add_argument('--lines', type=int, default=2, choices=(2, 3),
                    help='text lines per cap: 2 (14 px, ~220 chars/row) or '
                         '3 (10 px, ~469) -- see FLOW_PRESETS')
    ap.add_argument('--detail', action='store_true', help='per-keycap encoding')
    ap.add_argument('--no-answer-frame', action='store_true',
                    help='drop the border chrome on the answer keys (cost experiment)')
    ap.add_argument('--json', help='write the cost model here')
    args = ap.parse_args()
    globals()['NO_ANSWER_FRAME'] = args.no_answer_frame

    pk = next((p for p in (os.path.join(args.qmk, 'keyboards', 'polykybd'),
                           os.path.join(args.qmk, 'keyboards', 'handwired', 'polykybd'))
               if os.path.isdir(p)), None)
    if pk is None:
        raise SystemExit(f"no keyboards/polykybd under {args.qmk} — pass --qmk")

    matrices = parse_layout_matrix(os.path.join(pk, 'split72', 'keyboard.json'))
    keycodes = parse_layer_keycodes(
        os.path.join(pk, 'split72', 'keymaps', 'default', 'keymap.c'), "_L0")
    if len(matrices) != len(keycodes):
        raise SystemExit(f"layout/keymap mismatch: {len(matrices)} vs {len(keycodes)}")
    matrix_kc = dict(zip(matrices, keycodes))

    theme = Theme()
    painter = CapPainter(theme)
    for problem in check_fits(painter, args.lines):     # silent truncation is the
        print(f"  WARNING: {problem}")      # failure a mockup hides best
    renderer = KleRenderer(json.load(open(args.kle, encoding='utf-8')),
                           unit=args.unit, theme=theme, margin=args.margin,
                           exclude={m.strip() for m in args.exclude.split(';') if m.strip()})
    renderer.compact_halves(lambda mp: 'L' if int(mp.split(',')[0]) < 5 else 'R',
                            gap_px=args.gap)

    settings = DeviceSettings()
    os.makedirs(args.out_dir, exist_ok=True)
    specs = frames(matrix_kc, painter, args.lines)
    names = ("agent_1_typing", "agent_2_overview", "agent_3_question")
    costs = []
    for spec, name in zip(specs, names):
        content, arrays = to_state(spec, painter)
        img = renderer.render_frame(content)
        if args.scale != 1.0:
            img = img.resize((int(img.width * args.scale), int(img.height * args.scale)),
                             Image.LANCZOS)
        path = os.path.join(args.out_dir, name + ".png")
        img.save(path)
        costs.append(cost(arrays, settings, name))
        print(f"  wrote {path}  ({img.width}x{img.height})")

    # ---- the cost model -----------------------------------------------------
    # USB full speed: one 64-byte report per 1 ms frame. The wire is NOT the
    # bottleneck — the host's own pacing is: poly_kybd.send_overlays_mru() sleeps
    # delay_time_after_max_hid_messages (0.3 s) after every
    # max_hid_message_before_delay (15) reports, so a burst of 16 costs 300 ms
    # more than a burst of 15.
    PER_REPORT_MS, BURST, PAUSE_MS = 1.0, 15, 300
    # Split link (config.h full-duplex, SELECT_SOFT_SERIAL_SPEED 0 = 460800 8N1):
    # ~21.7 us/byte, so an image bound for the OTHER half also costs bridge time.
    BRIDGE_US_PER_BYTE = 21.7

    def line(name, imgs, img_reports, extra, note=""):
        total = img_reports + extra
        pauses = max(0, (total - 1) // BURST)
        ms = total * PER_REPORT_MS + pauses * PAUSE_MS
        print(f"  {name:<32} {imgs:>4} {total:>8} {pauses:>7} {ms:>8.0f}   {note}")

    overview, question = costs[1], costs[2]
    print(f"\n  device: {settings.HID_REPORT_SIZE} B reports, "
          f"{settings.MAX_PAYLOAD_BYTES_PER_REPORT} B payload, "
          f"{settings.OVERLAY_PLAIN_DATA_BYTES_TOTAL} B per keycap "
          f"({settings.OVERLAY_PLAIN_DATA_REPORT_COUNT} reports uncompressed)")
    print(f"  mapping: {settings.OVERLAY_MAPPING_INDICES_PER_REPORT // 2} pairs/report; "
          f"pool: {settings._overlay_mapping_pool_capacity} slots "
          f"(heaviest shipped app = 62 images)")
    print(f"  host pacing: sleep {PAUSE_MS} ms after every {BURST} reports\n")

    print(f"  {'step':<32} {'imgs':>4} {'reports':>8} {'pauses':>7} {'~ms':>8}   note")
    line("1 notify (badge appears)", 0, 0, 1, "legends+badge are firmware-drawn")
    line("2 open -> overview  COLD", overview["images"], overview["reports"], 2)
    line("  open -> overview  staged", 0, 0, 2, "images already in the pool")
    line("3 pick -> question  COLD", question["images"], question["reports"], 2)
    line("  pick -> question  staged", 0, 0, 2, "images already in the pool")
    line("4 answer -> back to typing", 0, 0, 2, "mapping + EXIT; pool keeps them")

    staged = overview["reports"] + question["reports"]
    bridge_ms = sum(b for *_, b in question["rows"]) * BRIDGE_US_PER_BYTE / 1000
    print(f"\n  pre-staging while the badge waits costs {staged} reports of background"
          f" traffic\n  and buys a tap-to-prompt of ~2 ms instead of "
          f"~{question['reports'] + 2 + PAUSE_MS:.0f} ms.")
    print(f"  if the prompt lands on the NON-master half, add ~{bridge_ms:.0f} ms of"
          f" split-link\n  bridge time for the question frame ({sum(b for *_, b in question['rows'])} compressed bytes).")

    if args.detail:
        for c in costs[1:]:
            print(f"\n  {c['label']}:")
            for mp, n, kind, nbytes in c["rows"]:
                print(f"    {mp:>5}  {n} report(s)  {kind:<11} {nbytes:>4} B compressed")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(costs, fh, indent=2, default=str)
        print(f"  wrote {args.json}")


if __name__ == '__main__':
    main()
