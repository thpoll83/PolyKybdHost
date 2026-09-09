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

* **The outline is the CASE, not the board** -- `parts/case/outline_polykybd_split72_*.svg`,
  the contour `case_polykybd_split72_lr.scad` extrudes, which is the `Edge.Cuts`
  polygon offset outward by `case_wall_thickness + pcb_clearance` = 1.65 mm with
  rounded corners. Taking the board instead drew the plate 1.65 mm too small on
  every side, which is most visible at the thumbs, where the keycaps overhang a
  bare PCB edge and do not overhang the case. The shipped SVG is used verbatim
  rather than re-deriving the offset: it IS the extruded contour, rounded corners
  and all. It is placed by a translation fitted to the board's own bounding box,
  and then every one of its points is checked to sit `CASE_OFFSET_MM` outside the
  `Edge.Cuts` polygon -- which is what proves the SVG belongs to this board and
  that the translation is right. `Edge.Cuts` (16 segments per half, chained into
  one closed polygon) is still read, as the yardstick for that check.
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

#: How far the case wall stands proud of the board: `case_wall_thickness`
#: (1.5) + `pcb_clearance` (0.15), from `parts/case/case_polykybd_split72_lr.scad`.
#: ⚠️ The other case variants are NOT all this number -- `case_polysplit72_right2`
#: and `right_side` use a 0.25 clearance, i.e. 1.75 -- so this tracks the split72
#: left+right case specifically, which is the one the shipped SVGs come from.
CASE_OFFSET_MM = 1.65

#: How far a point of the shipped case outline may sit from `CASE_OFFSET_MM`
#: before the fit is refused. Measured on the shipped SVGs: 1.647..1.654, the
#: spread being the polygon approximation of the rounded corners.
CASE_OFFSET_TOL_MM = 0.05

#: 0.96" 128x64 status panel (FPW096W001Z0 and pin-compatible parts): glass
#: extent and lit area, in mm. Drawn as two rectangles so the editor shows the
#: module AND the part of it that actually displays anything.
PANEL_MM = (26.70, 19.26)
ACTIVE_MM = (21.74, 10.86)

#: Rows 0-4 are the left half, 5-9 the right -- the split the KLE and the two
#: board files share.
LEFT_ROWS = range(0, 5)

#: The extruded case contour per half, as shipped by `case_polykybd_split72_lr.scad`.
#: ⚠️ The left file really is spelled `leftt`.
CASE_SVG = {"left": "outline_polykybd_split72_leftt.svg",
            "right": "outline_polykybd_split72_right.svg"}

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


def svg_polygon(path):
    """The single closed path of an OpenSCAD-exported 2D outline, in its own mm."""
    text = path.read_text(encoding="utf-8")
    try:
        d = text.split('\n<path d="', 1)[1].split('"', 1)[0]
    except IndexError:
        raise SystemExit("%s carries no <path d=...>" % path)
    pts = [(float(a), float(b))
           for a, b in re.findall(r"([-\d.]+),([-\d.]+)", d)]
    if len(pts) < 3:
        raise SystemExit("%s: %d-point outline" % (path, len(pts)))
    return pts


def _edge_distance(poly, pt):
    """Shortest distance from `pt` to the polygon boundary."""
    best = float("inf")
    for i in range(len(poly)):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % len(poly)]
        dx, dy = bx - ax, by - ay
        if dx == 0.0 and dy == 0.0:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((pt[0] - ax) * dx + (pt[1] - ay) * dy)
                             / (dx * dx + dy * dy)))
        best = min(best, math.hypot(pt[0] - (ax + t * dx), pt[1] - (ay + t * dy)))
    return best


def place_case_outline(case_pts, edge_poly, side):
    """Move the case SVG into the board's frame, and prove it belongs there.

    The SVG is drawn in OpenSCAD's own coordinates, so it needs a translation --
    fitted from the bounding boxes, since the case is the board grown uniformly
    by `CASE_OFFSET_MM`. The fit is then CHECKED rather than trusted: every point
    must sit that far outside `Edge.Cuts`. A wrong translation, a mirrored SVG or
    the outline of a different board all fail it by millimetres.
    """
    ex = [p[0] for p in edge_poly]
    ey = [p[1] for p in edge_poly]
    sx = [p[0] for p in case_pts]
    sy = [p[1] for p in case_pts]
    tx = (min(ex) - CASE_OFFSET_MM) - min(sx)
    ty = (min(ey) - CASE_OFFSET_MM) - min(sy)
    moved = [(x + tx, y + ty) for x, y in case_pts]

    span = ((max(sx) - min(sx)) - (max(ex) - min(ex)),
            (max(sy) - min(sy)) - (max(ey) - min(ey)))
    for grew in span:
        if abs(grew - 2 * CASE_OFFSET_MM) > CASE_OFFSET_TOL_MM:
            raise SystemExit("%s: the case outline is %.3f mm wider than the board, "
                             "expected %.3f -- wrong SVG, or the case grew"
                             % (side, grew, 2 * CASE_OFFSET_MM))

    dists = [_edge_distance(edge_poly, p) for p in moved]
    worst = max(abs(d - CASE_OFFSET_MM) for d in dists)
    if worst > CASE_OFFSET_TOL_MM:
        raise SystemExit("%s: a case outline point sits %.3f mm off the expected "
                         "%.2f mm offset -- the SVG does not match this board"
                         % (side, worst, CASE_OFFSET_MM))
    return moved, (min(dists), max(dists))


#: The bezel the editor draws: ONE key-to-case margin on all four sides.
#: ⚠️ The real case is not even -- measured W 6.4 / E 3.6 / N 8.8 / S 6.2 mm on the
#: left half -- so this is a deliberate STYLISATION, and it is the same one the KLE
#: already applies to the KEYS. The KLE draws the outer column 1.25U wide over a
#: 1.25U pitch where the board has 1U switches, and it approximates the thumb
#: clusters, so a photographically exact case around stylised keys reads as a
#: crooked bezel rather than as accuracy. 0.33U is the mean of the eight true
#: margins, so the outline barely moves; the shape, its rounded corners and its
#: provenance check are untouched.
BEZEL_U = 0.33

#: How far `normalise_bezel` may stretch the case to reach that. It is a fit, not a
#: licence to reshape: past this the key field and the case disagree about what
#: keyboard they describe, which is a bug upstream rather than a bezel to even out.
MAX_BEZEL_STRETCH = 0.15

#: Grid step and key clearance for the free-space search that places a status
#: panel. The step only has to resolve a bezel, and the search is O(rows^2).
FREE_STEP_U = 0.05
FREE_KEY_CLEARANCE_U = 0.06

#: How far `case_top_over` stays clear of the ends it measures between -- see there.
CASE_TOP_INSET_U = 0.02


def key_corners(k):
    """The four corners of a key in layout units, rotation applied."""
    pts = [(k["x"], k["y"]), (k["x"] + k["w"], k["y"]),
           (k["x"] + k["w"], k["y"] + k["h"]), (k["x"], k["y"] + k["h"])]
    r = k.get("r", 0.0)
    if not r:
        return pts
    rx, ry, a = k.get("rx", 0.0), k.get("ry", 0.0), math.radians(r)
    out = []
    for x, y in pts:
        dx, dy = x - rx, y - ry
        out.append((rx + dx * math.cos(a) - dy * math.sin(a),
                    ry + dx * math.sin(a) + dy * math.cos(a)))
    return out


def normalise_bezel(pts, key_box, side):
    """Fit the case outline around the key field with one margin on all sides.

    An axis-aligned scale + translate, so the silhouette and its rounded corners
    survive; only the four margins move. Returns the moved points and a mapper for
    anything else that has to follow them into the new frame.
    """
    ox0, ox1 = min(p[0] for p in pts), max(p[0] for p in pts)
    oy0, oy1 = min(p[1] for p in pts), max(p[1] for p in pts)
    kx0, kx1, ky0, ky1 = key_box
    tx0, tx1 = kx0 - BEZEL_U, kx1 + BEZEL_U
    ty0, ty1 = ky0 - BEZEL_U, ky1 + BEZEL_U
    sx = (tx1 - tx0) / (ox1 - ox0)
    sy = (ty1 - ty0) / (oy1 - oy0)
    for scale, axis in ((sx, "x"), (sy, "y")):
        if abs(scale - 1.0) > MAX_BEZEL_STRETCH:
            raise SystemExit("%s: evening the bezel would stretch %s by %.1f%% -- the "
                             "case and the key field do not describe the same board"
                             % (side, axis, (scale - 1.0) * 100.0))

    def move(x, y):
        return (tx0 + (x - ox0) * sx, ty0 + (y - oy0) * sy)

    return [move(x, y) for x, y in pts], move, (sx, sy)


def _row_spans(poly, y):
    """The x intervals where the horizontal line at `y` is inside `poly`."""
    xs = []
    for i in range(len(poly)):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % len(poly)]
        if (ay > y) != (by > y):
            xs.append(ax + (y - ay) / (by - ay) * (bx - ax))
    xs.sort()
    return list(zip(xs[0::2], xs[1::2]))


def _top_at(poly, x):
    """The polygon's top boundary at `x` (its smallest y there), or None."""
    ys = []
    for i in range(len(poly)):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % len(poly)]
        if (ax > x) != (bx > x):
            ys.append(ay + (x - ax) / (bx - ax) * (by - ay))
    return min(ys) if ys else None


def case_top_over(outline, x0, x1, samples=41):
    """The LOWEST the case's top edge gets across [x0, x1].

    The lowest, because the edge slopes: anything hung below this clears the
    boundary for its whole width, which is what lets a panel be placed from the
    case rather than from the search rectangle (whose top is chosen for area, so
    it sits further down wherever the case narrows).
    """
    # ⚠️ Inset from both ends. A sample landing exactly on the polygon's extreme x
    # sits on a vertex, where the crossing test degenerates and returns the CORNER
    # rather than the top edge -- which pushed one half's panel 0.085U below the
    # other's, on two boards that are mirror images. The inset is 0.4 mm, well
    # under anything the sloped corner can hide.
    lo, hi = x0 + CASE_TOP_INSET_U, x1 - CASE_TOP_INSET_U
    if hi <= lo:
        lo, hi = (x0 + x1) / 2.0, (x0 + x1) / 2.0
    tops = [t for t in (_top_at(outline, lo + (hi - lo) * i / (samples - 1.0))
                        for i in range(samples)) if t is not None]
    return max(tops) if tops else None


def free_rect_at(anchor, outline, blockers):
    """The largest free rectangle CONTAINING `anchor`, inside `outline`, clear of
    `blockers`.

    The anchor is what keeps this honest: it is the board's own `J39` connector, so
    the hardware still decides WHERE the panel goes and this only decides how much
    room it has there. Returns (x0, y0, x1, y1) or None when the anchor is covered.
    """
    ox0, ox1 = min(p[0] for p in outline), max(p[0] for p in outline)
    oy0, oy1 = min(p[1] for p in outline), max(p[1] for p in outline)
    rows = int((oy1 - oy0) / FREE_STEP_U)
    if rows < 3:
        return None
    ar = int((anchor[1] - oy0) / FREE_STEP_U)
    if not 0 <= ar < rows:
        return None

    def span_at(r):
        """The free interval of row r that contains the anchor's x, or None."""
        y = oy0 + (r + 0.5) * FREE_STEP_U
        inside = [s for s in _row_spans(outline, y) if s[0] <= anchor[0] <= s[1]]
        if not inside:
            return None
        lo, hi = inside[0]
        for b in blockers:
            bx0, by0, bx1, by1 = b
            if by0 <= y <= by1:
                if bx0 <= anchor[0] <= bx1:
                    return None
                if bx1 < anchor[0]:
                    lo = max(lo, bx1)
                else:
                    hi = min(hi, bx0)
        return (lo, hi) if hi > lo else None

    spans = [span_at(r) for r in range(rows)]
    if spans[ar] is None:
        return None

    def accumulate(order):
        acc, lo, hi = {}, spans[ar][0], spans[ar][1]
        for r in order:
            if spans[r] is None:
                break
            lo, hi = max(lo, spans[r][0]), min(hi, spans[r][1])
            if hi <= lo:
                break
            acc[r] = (lo, hi)
        return acc

    up = accumulate(range(ar, -1, -1))
    dn = accumulate(range(ar, rows))
    best = None
    for t, (tlo, thi) in up.items():
        for b, (blo, bhi) in dn.items():
            lo, hi = max(tlo, blo), min(thi, bhi)
            if hi <= lo:
                continue
            area = (hi - lo) * (b - t + 1) * FREE_STEP_U
            if best is None or area > best[0]:
                best = (area, lo, oy0 + t * FREE_STEP_U, hi, oy0 + (b + 1) * FREE_STEP_U)
    if best is None:
        return None
    return best[1], best[2], best[3], best[4]


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


def exact_span(anchor_x, outline, blockers, y0, y1, samples=41):
    """The free x interval containing `anchor_x` across the whole band [y0, y1].

    The grid search resolves a corner to `FREE_STEP_U`, which leaves a panel about
    a millimetre short of the case it is supposed to meet. This re-measures the one
    band the panel actually occupies, off the polygon rather than off the grid, so
    "grow until it touches" means touching.
    """
    lo, hi = -1e9, 1e9
    for i in range(samples):
        y = y0 + (y1 - y0) * i / (samples - 1.0)
        inside = [sp for sp in _row_spans(outline, y) if sp[0] <= anchor_x <= sp[1]]
        if not inside:
            return None
        lo, hi = max(lo, inside[0][0]), min(hi, inside[0][1])
    for bx0, by0, bx1, by1 in blockers:
        if by1 <= y0 or by0 >= y1:
            continue
        if bx0 <= anchor_x <= bx1:
            return None
        if bx1 < anchor_x:
            lo = max(lo, bx1)
        else:
            hi = min(hi, bx0)
    return (lo, hi) if hi > lo else None


def place_display(anchor, outline, blockers, side):
    """Size and position one status panel in the free corner its FPC sits in.

    The MODULE is scaled to span that corner -- that is what sets the screen's size
    and where it sits -- and then its SIDE BEZEL IS SIMPLY NOT DRAWN. ⚠️ Removing it
    changes the GLASS only: the screen keeps the size AND the position the uniform
    fit gave it, so the panel now stops one module bezel short of the housing rather
    than meeting it. Two things that both look like the same instruction and are not:
    widening the screen to fill the glass grows the lit area by the bezel it was
    meant to delete, and sliding the narrowed panel flush moves a screen that was
    already placed. Glass survives above and below, in the module's own proportion.

    Position comes from the corner too, not from the connector: the FPC is at the
    BOARD's height, low in the corner, which leaves the panel looking dropped. It
    says which corner, not where in it. Falls back to the module at the connector
    when the corner cannot be measured.
    """
    panel = (PANEL_MM[0] / UNIT_MM, PANEL_MM[1] / UNIT_MM)
    active = (ACTIVE_MM[0] / UNIT_MM, ACTIVE_MM[1] / UNIT_MM)
    cx, cy, scale = anchor[0], anchor[1], 1.0

    rect = free_rect_at(anchor, outline, blockers)
    if rect is None:
        print("%-5s no free corner measured at J39 -- panel left at the connector"
              % side)
    else:
        rx0, ry0, rx1, ry1 = rect

        def fit(lo, hi):
            """The scale the MODULE would need to span [lo, hi]."""
            return min((hi - lo) / panel[0], (ry1 - ry0) / panel[1])

        def hang(x_lo, x_hi, tall):
            """Top edge for a panel spanning [x_lo, x_hi].

            One bezel under the CASE's top edge, not centred in the corner: the
            corner runs all the way down to the thumb cluster, so centring drops the
            panel below the top key row and it reads as having slipped. One bezel is
            the gap the plate keeps everywhere else, so the panel lines up with it.
            """
            top = case_top_over(outline, x_lo, x_hi)
            if top is None:
                return (ry0 + ry1 - tall) / 2.0
            y = top + BEZEL_U
            for bx0, by0, bx1, by1 in blockers:      # never into a keycap
                if bx1 > x_lo and bx0 < x_hi and by1 > y and by0 < y + tall:
                    y = max(y, by1)
            return min(y, ry1 - tall)

        def lay_out(lo, hi):
            """The screen's own span, CENTRED in the corner the module spans.

            The module's side bezel is symmetric, so this is exactly where the
            screen sat when the whole module was drawn -- dropping the bezel from
            the picture must not move what is left of it.
            """
            k = fit(lo, hi)
            tall = panel[1] * k
            mid, half = (lo + hi) / 2.0, active[0] * k / 2.0
            return k, tall, mid - half, mid + half, hang(mid - half, mid + half, tall)

        scale, height, x0, x1, y_top = lay_out(rx0, rx1)
        # The grid search resolves the corner to FREE_STEP_U, about a millimetre, so
        # re-measure the band the panel actually occupies -- that is what the module
        # is sized against, and a millimetre of it is a millimetre of screen.
        refined = exact_span(anchor[0], outline, blockers, y_top, y_top + height)
        if refined is not None:
            scale, height, x0, x1, y_top = lay_out(*refined)
        cx, cy = (x0 + x1) / 2.0, y_top + height / 2.0

    # `w == aw`: the side bezel is not drawn, so the glass is exactly as wide as the
    # screen. `h` and `ah` keep the module's own vertical proportion.
    return {
        "cx": round(cx, 4), "cy": round(cy, 4),
        "w": round(active[0] * scale, 4), "h": round(panel[1] * scale, 4),
        "aw": round(active[0] * scale, 4), "ah": round(active[1] * scale, 4),
    }


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

        edge = edge_polygon(text)
        case_svg = hw / "parts" / "case" / CASE_SVG[side]
        case_mm, case_fit = place_case_outline(svg_polygon(case_svg), edge, side)
        case_size = (max(x for x, _ in case_mm) - min(x for x, _ in case_mm),
                     max(y for _, y in case_mm) - min(y for _, y in case_mm))

        corners = [c for k in key_matrix.values() if k["row"] in rows
                   for c in key_corners(k)]
        key_box = (min(c[0] for c in corners), max(c[0] for c in corners),
                   min(c[1] for c in corners), max(c[1] for c in corners))
        outline, to_even, stretch = normalise_bezel(
            [to_u(x, y) for x, y in case_mm], key_box, side)

        j39 = [(x, y) for lib, ref, x, y, _r in fps if ref == "J39"]
        if len(j39) != 1:
            raise SystemExit("%s: expected exactly one J39 status-display FPC, found %d"
                             % (side, len(j39)))
        anchor = to_even(*to_u(*j39[0]))
        blockers = []
        for k in key_matrix.values():
            if k["row"] not in rows:
                continue
            c = key_corners(k)
            blockers.append((min(p[0] for p in c) - FREE_KEY_CLEARANCE_U,
                             min(p[1] for p in c) - FREE_KEY_CLEARANCE_U,
                             max(p[0] for p in c) + FREE_KEY_CLEARANCE_U,
                             max(p[1] for p in c) + FREE_KEY_CLEARANCE_U))
        displays = [place_display(anchor, outline, blockers, side)]

        halves.append({
            "side": side,
            "outline": outline,
            "displays": displays,
            "fit": {"worst_residual_u": round(worst, 4),
                    "mean_residual_u": round(mean, 4),
                    "switches": len(switches),
                    "case_offset_mm": [round(case_fit[0], 4), round(case_fit[1], 4)],
                    "case_mm": [round(case_size[0], 3), round(case_size[1], 3)],
                    "bezel_stretch": [round(stretch[0], 4), round(stretch[1], 4)]},
        })

    return {
        "board": "split72",
        "unit_mm": UNIT_MM,
        "case_offset_mm": CASE_OFFSET_MM,
        "bezel_u": BEZEL_U,
        "source": _source(hw),
        "note": ("Derived from the PolyKybd hardware repo by "
                 "scripts/export_board_outline.py -- do not hand-edit. The "
                 "outline is the CASE contour (the board grown by "
                 "case_wall_thickness + pcb_clearance), not the bare PCB edge. "
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
