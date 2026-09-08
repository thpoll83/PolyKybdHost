#!/usr/bin/env python3
"""Export the split72 board outline + status-display placement for the layout editor.

The layout editor draws 74 tiles floating in space. This adds the thing they
sit on: the real board outline of each half, and the two optional status
displays. Both are DERIVED from the hardware repo's KiCad boards rather than
drawn by hand, because a hand-traced outline is a second opinion that goes
stale silently -- the same failure `export_preview_data.py` exists to avoid.

    python scripts/export_board_outline.py                # sibling PolyKybd
    python scripts/export_board_outline.py --hardware DIR
    python scripts/export_board_outline.py --check        # is the shipped copy current?

What comes out of the boards, and why each is trustworthy:

* **The outline** is the `Edge.Cuts` layer -- 16 segments per half, chained into
  one closed polygon.
* **The mm -> key-unit transform** is a pure translation at 19.05 mm/U (the boards
  lay their switches on that pitch with no board rotation). The offset is fitted
  by trying every (switch, KLE key) pairing and keeping the one that lines up all
  37 switches best, so the fit VERIFIES itself -- the residuals are written into
  the JSON and checked below. It is not exact everywhere and cannot be: the KLE
  draws the outer column as 1.25U-wide keys with a 0.25U gap where the board has
  1U switches on a 1.25U pitch, so those keys sit 0.125U (2.4 mm) out by design.
* **The status display** hangs off the 30-pin FPC (`J39`), which sits at the same
  height on both halves, mirrored about the layout's centre line. The module is
  placed on that connector: a 0.96" panel lands exactly in the free corner
  between the top rows and the inner board edge, which is presumably why the
  board reserves that corner.
"""
import argparse
import json
import math
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polyhost.kle.kle_praser import parse_kle                        # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "polyhost" / "res" / "board_outline.json"
KLE = pathlib.Path(__file__).resolve().parent.parent / "polyhost" / "res" / "polykybd-split72.json"

#: Key pitch. 1U on every PolyKybd board, and the whole mm <-> unit conversion.
UNIT_MM = 19.05

#: 0.96" 128x64 status panel (FPW096W001Z0 and pin-compatible parts): glass
#: extent and lit area, in mm. Drawn as two rectangles so the editor shows the
#: module AND the part of it that actually displays anything.
PANEL_MM = (26.70, 19.26)
ACTIVE_MM = (21.74, 10.86)

#: Rows 0-4 are the left half, 5-9 the right -- the split the KLE and the two
#: board files share.
LEFT_ROWS = range(0, 5)

#: A fit is only believable if it lines the switches up, so these bound it.
#: Measured on the shipped boards: 31 of 37 switches per half land EXACTLY on
#: their key, the outer column is out by 0.125U and the outer thumbs by up to
#: 0.24U -- both the KLE's deliberate stylisation of a shape it draws in whole
#: key units, not drift. The bounds sit just above that, and the bijection
#: check below is the stronger signal: a wrong offset pairs two switches with
#: one key long before it moves the mean.
MAX_RESIDUAL_U = 0.30
MAX_MEAN_RESIDUAL_U = 0.05


def hardware_dir(explicit):
    if explicit:
        return pathlib.Path(explicit)
    return pathlib.Path(__file__).resolve().parent.parent.parent / "PolyKybd"


def _blocks(text, head):
    """Yield each balanced `(<head> ...)` s-expression in a .kicad_pcb."""
    pat = re.compile(r"\((%s)\b" % "|".join(head))
    i = 0
    while True:
        m = pat.search(text, i)
        if not m:
            return
        start, depth, j = m.start(), 0, m.start()
        while True:
            c = text[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        yield m.group(1), text[start:j + 1]
        i = j + 1


def footprints(text):
    """(library, reference, x, y, rotation) for every footprint on a board."""
    out = []
    for _, blk in _blocks(text, ["footprint"]):
        lib = re.match(r'\(footprint "([^"]+)"', blk).group(1)
        at = re.search(r"\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", blk)
        ref = re.search(r'"Reference"\s*"([^"]+)"', blk)
        out.append((lib, ref.group(1) if ref else "?",
                    float(at.group(1)), float(at.group(2)), float(at.group(3) or 0)))
    return out


def edge_polygon(text):
    """Chain the Edge.Cuts segments into one closed polygon, in mm."""
    segs = []
    for kind, blk in _blocks(text, ["gr_line", "gr_arc"]):
        layer = re.search(r'\(layer "([^"]+)"', blk)
        if not layer or layer.group(1) != "Edge.Cuts":
            continue
        if kind != "gr_line":
            raise SystemExit("Edge.Cuts carries a %s; this exporter only chains "
                             "straight segments" % kind)
        a = re.search(r"\(start ([-\d.]+) ([-\d.]+)\)", blk)
        b = re.search(r"\(end ([-\d.]+) ([-\d.]+)\)", blk)
        segs.append(((float(a.group(1)), float(a.group(2))),
                     (float(b.group(1)), float(b.group(2)))))
    if not segs:
        raise SystemExit("no Edge.Cuts segments found")

    def close(p, q):
        return abs(p[0] - q[0]) < 1e-3 and abs(p[1] - q[1]) < 1e-3

    ring = list(segs.pop(0))
    while segs:
        for i, (a, b) in enumerate(segs):
            if close(ring[-1], a):
                ring.append(b)
            elif close(ring[-1], b):
                ring.append(a)
            else:
                continue
            segs.pop(i)
            break
        else:
            raise SystemExit("Edge.Cuts does not chain into a single loop "
                             "(%d segments left over)" % len(segs))
    if not close(ring[0], ring[-1]):
        raise SystemExit("Edge.Cuts loop does not close")
    return ring[:-1]


def kle_centres(key_matrix, rows):
    """Centre of every key of one half, in key units, rotation applied."""
    out = {}
    for name, k in key_matrix.items():
        if k["row"] not in rows:
            continue
        cx, cy = k["x"] + k["w"] / 2.0, k["y"] + k["h"] / 2.0
        r = k.get("r", 0.0)
        if r:
            rx, ry = k.get("rx", 0.0), k.get("ry", 0.0)
            a = math.radians(r)
            dx, dy = cx - rx, cy - ry
            cx = rx + dx * math.cos(a) - dy * math.sin(a)
            cy = ry + dx * math.sin(a) + dy * math.cos(a)
        out[name] = (cx, cy)
    return out


def fit_offset(switches_mm, centres_u):
    """Find the mm -> unit translation, by trying every switch/key pairing.

    Scale is fixed (19.05 mm/U) and the boards carry no rotation, so the only
    unknown is where the board's origin sits in the layout. Every candidate is
    scored against ALL the switches, so the winner is the one that explains the
    whole board and the residuals below say how well.
    """
    pts = [(x / UNIT_MM, y / UNIT_MM) for _, x, y in switches_mm]
    targets = list(centres_u.values())
    best = None
    for px, py in pts:
        for tx, ty in targets:
            ox, oy = tx - px, ty - py
            total = 0.0
            for qx, qy in pts:
                u, v = qx + ox, qy + oy
                total += min((u - ax) ** 2 + (v - ay) ** 2 for ax, ay in targets)
            if best is None or total < best[0]:
                best = (total, ox, oy)
    _, ox, oy = best
    resid, matched = [], []
    for qx, qy in pts:
        u, v = qx + ox, qy + oy
        i = min(range(len(targets)),
                key=lambda k: (u - targets[k][0]) ** 2 + (v - targets[k][1]) ** 2)
        ax, ay = targets[i]
        resid.append(math.sqrt((u - ax) ** 2 + (v - ay) ** 2))
        matched.append(i)
    return ox, oy, resid, matched


def build(hw):
    kle = json.loads(KLE.read_text(encoding="utf-8"))
    _rows, _cols, key_matrix = parse_kle(kle)

    halves = []
    for side, rows in (("left", LEFT_ROWS), ("right", range(5, 10))):
        pcb = hw / "poly_kybd" / ("poly_kybd_split72_%s.kicad_pcb" % side)
        text = pcb.read_text(encoding="utf-8")
        fps = footprints(text)

        switches = [(ref, x, y) for lib, ref, x, y, _r in fps
                    if "Kailh" in lib or "PolyJog" in lib]
        centres = {n: c for n, c in kle_centres(key_matrix, rows).items()}
        if len(switches) != len(centres):
            raise SystemExit("%s: %d switches on the board vs %d keys in the KLE"
                             % (side, len(switches), len(centres)))
        ox, oy, resid, matched = fit_offset(switches, centres)
        worst, mean = max(resid), sum(resid) / len(resid)
        if worst > MAX_RESIDUAL_U or mean > MAX_MEAN_RESIDUAL_U:
            raise SystemExit("%s: switch fit is off (worst %.3fU, mean %.3fU) -- the "
                             "board and the KLE no longer describe the same keyboard"
                             % (side, worst, mean))
        if len(set(matched)) != len(matched):
            raise SystemExit("%s: the fit pairs two switches with the same key, so it "
                             "is not the right offset" % side)

        def to_u(x, y):
            return [round(x / UNIT_MM + ox, 4), round(y / UNIT_MM + oy, 4)]

        outline = [to_u(x, y) for x, y in edge_polygon(text)]

        j39 = [(x, y) for lib, ref, x, y, _r in fps if ref == "J39"]
        if len(j39) != 1:
            raise SystemExit("%s: expected exactly one J39 status-display FPC, found %d"
                             % (side, len(j39)))
        dx, dy = to_u(*j39[0])
        displays = [{
            "cx": dx, "cy": dy,
            "w": round(PANEL_MM[0] / UNIT_MM, 4), "h": round(PANEL_MM[1] / UNIT_MM, 4),
            "aw": round(ACTIVE_MM[0] / UNIT_MM, 4), "ah": round(ACTIVE_MM[1] / UNIT_MM, 4),
        }]

        halves.append({
            "side": side,
            "outline": outline,
            "displays": displays,
            "fit": {"worst_residual_u": round(worst, 4),
                    "mean_residual_u": round(mean, 4),
                    "switches": len(switches)},
        })

    return {
        "board": "split72",
        "unit_mm": UNIT_MM,
        "source": _source(hw),
        "note": ("Derived from the PolyKybd KiCad boards by "
                 "scripts/export_board_outline.py -- do not hand-edit. "
                 "Coordinates are key units in the same frame as "
                 "res/polykybd-split72.json."),
        "halves": halves,
    }


def _source(hw):
    try:
        sha = subprocess.run(["git", "-C", str(hw), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        sha = "unknown"
    return "PolyKybd@%s" % sha


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hardware", help="path to a PolyKybd checkout")
    ap.add_argument("--check", action="store_true",
                    help="re-derive and report drift instead of writing")
    args = ap.parse_args()

    data = build(hardware_dir(args.hardware))
    text = json.dumps(data, indent=1, sort_keys=True) + "\n"

    if args.check:
        if not OUT.exists():
            print("MISSING %s" % OUT)
            return 1
        # The source sha moves with the hardware checkout and says nothing about
        # the geometry, so compare everything else.
        old = json.loads(OUT.read_text(encoding="utf-8"))
        new = json.loads(text)
        old.pop("source", None)
        new.pop("source", None)
        if old != new:
            print("STALE %s" % OUT)
            return 1
        print("current: %s" % OUT)
        return 0

    OUT.write_text(text, encoding="utf-8")
    for half in data["halves"]:
        print("%-5s %2d outline points, %d display(s), fit worst %.3fU mean %.3fU"
              % (half["side"], len(half["outline"]), len(half["displays"]),
                 half["fit"]["worst_residual_u"], half["fit"]["mean_residual_u"]))
    print("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
