"""The board the layout editor draws its keys on.

Two kinds of check here. The cheap ones cover the loader's fail-soft contract.
The one that earns its keep is `KeysSitOnTheBoardTest`: it walks every key of
the shipped KLE and asserts the key is inside its half's outline polygon. That
is the only thing that can catch a wrong mm -> key-unit offset, and a wrong
offset is exactly what a regenerated export could introduce -- the picture
would still draw, just with the board somewhere else.
"""
import json
import math
import pathlib
import tempfile
import unittest

from polyhost.kle.kle_praser import parse_kle
from polyhost.services import board_outline as bo

KLE = pathlib.Path(__file__).resolve().parents[2] / "polyhost" / "res" / "polykybd-split72.json"

LEFT_ROWS = range(0, 5)


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


def inside(poly, pt):
    """Ray-cast point-in-polygon; the outlines are simple closed loops."""
    x, y = pt
    hit = False
    for i in range(len(poly)):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % len(poly)]
        if (ay > y) != (by > y):
            if x < ax + (y - ay) / (by - ay) * (bx - ax):
                hit = not hit
    return hit


#: The 0.96" module the exporter draws, in mm -- glass height and lit height. The
#: WIDTHS are deliberately absent: the panel drops its side bezel, so its width is
#: whatever its corner is and only the vertical proportion survives.
PANEL_H_MM = 19.26
ACTIVE_H_MM = 10.86

#: The corner search's grid step in `scripts/export_board_outline.py`; nothing
#: placed from it can be pinned finer than this.
GRID_U = 0.06


def boundary_y_at(poly, x):
    """The polygon's TOP boundary at `x` (its smallest y there), or None."""
    ys = []
    for i in range(len(poly)):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % len(poly)]
        if (ax > x) != (bx > x):
            ys.append(ay + (x - ax) / (bx - ax) * (by - ay))
    return min(ys) if ys else None


def edge_distance(poly, pt):
    """Shortest distance from `pt` to the polygon boundary, in key units."""
    best = float("inf")
    for i in range(len(poly)):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % len(poly)]
        dx, dy = bx - ax, by - ay
        if dx == 0.0 and dy == 0.0:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((pt[0] - ax) * dx + (pt[1] - ay) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(pt[0] - (ax + t * dx), pt[1] - (ay + t * dy)))
    return best


class LoadTest(unittest.TestCase):
    def test_the_shipped_board_loads(self):
        board = bo.load()
        self.assertIsNotNone(board, "polyhost/res/board_outline.json is missing or broken")
        self.assertEqual("split72", board.board)
        self.assertEqual({"left", "right"}, {h.side for h in board.halves})

    def test_a_missing_file_costs_the_picture_and_nothing_else(self):
        self.assertIsNone(bo.load(pathlib.Path(tempfile.gettempdir()) / "no-such-board.json"))

    def test_malformed_json_is_not_an_exception(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write('{"halves": [{"side": "left", "outline": [[0, 0], [1, 1]]}]}')
            path = fh.name
        self.assertIsNone(bo.load(path), "a 2-point outline is not a polygon")

    def test_rects_are_centred_on_the_stated_point(self):
        d = bo.Display(cx=10.0, cy=4.0, w=2.0, h=1.0, aw=1.0, ah=0.5)
        self.assertEqual((9.0, 3.5, 2.0, 1.0), d.rect)
        self.assertEqual((9.5, 3.75, 1.0, 0.5), d.active_rect)


class KeysSitOnTheBoardTest(unittest.TestCase):
    """Every key of a half is inside that half's outline -- the check that the
    mm -> key-unit offset in the export is right."""

    @classmethod
    def setUpClass(cls):
        cls.board = bo.load()
        if cls.board is None:
            raise unittest.SkipTest("no board outline shipped")
        _rows, _cols, cls.keys = parse_kle(json.loads(KLE.read_text(encoding="utf-8")))
        cls.poly = {h.side: h.outline for h in cls.board.halves}

    def test_every_key_CENTRE_is_on_its_own_half(self):
        """Strict: a centre off the board means the offset is simply wrong."""
        for name, k in self.keys.items():
            side = "left" if k["row"] in LEFT_ROWS else "right"
            centre = (k["x"] + k["w"] / 2.0, k["y"] + k["h"] / 2.0)
            self.assertTrue(inside(self.poly[side], centre),
                            "key %s (%.2f, %.2f) is off the %s board"
                            % (name, centre[0], centre[1], side))

    def test_NO_key_hangs_over_the_edge_at_all(self):
        """Zero, not a tolerance -- and the history is why that is now sayable.

        It was 0.10U (1.9 mm) against the bare PCB edge, and 0.014U once the CASE
        replaced it. Evening the bezel lifted the last two thumb corners inside, so
        the bound is the real one. The visible symptom of losing this is keycaps
        overhanging the plate at the thumbs, which they do not do on the keyboard.
        """
        for name, k in self.keys.items():
            side = "left" if k["row"] in LEFT_ROWS else "right"
            for corner in key_corners(k):
                self.assertTrue(inside(self.poly[side], corner),
                                "key %s corner %s hangs %.3fU off the %s board"
                                % (name, tuple(round(c, 2) for c in corner),
                                   edge_distance(self.poly[side], corner), side))

    def test_the_bezel_is_the_SAME_on_all_four_sides(self):
        """The contract the outline is fitted to, and the check a containment
        test cannot make on its own.

        A board that is merely BIG enough contains every key however it is
        translated -- measured, shifting both outlines 0.25U inward still passes
        containment, because the inner edge has that much slack. Pinning the
        margin instead catches a translation on the first edge it moves.

        The case's OWN margins are uneven (W 6.4 / E 3.6 / N 8.8 / S 6.2 mm on the
        left half), so this is the exporter's deliberate fit, not a measurement of
        the hardware -- see `normalise_bezel`.
        """
        for half in self.board.halves:
            rows = LEFT_ROWS if half.side == "left" else range(5, 10)
            corners = [c for k in self.keys.values() if k["row"] in rows
                       for c in key_corners(k)]
            kx = [c[0] for c in corners]
            ky = [c[1] for c in corners]
            ox = [p[0] for p in half.outline]
            oy = [p[1] for p in half.outline]
            margins = {"left": min(kx) - min(ox), "right": max(ox) - max(kx),
                       "top": min(ky) - min(oy), "bottom": max(oy) - max(ky)}
            for side, margin in margins.items():
                self.assertAlmostEqual(
                    margin, self.board.bezel_u, delta=0.005,
                    msg="%s board: %.3fU of bezel at the %s edge, expected %.3fU"
                        % (half.side, margin, side, self.board.bezel_u))

    def test_the_outline_is_the_CASE_not_the_bare_board(self):
        """Pins the one number that separates the two.

        `Edge.Cuts` measures 182.0 x 129.0 mm; the case that
        `case_polykybd_split72_lr.scad` extrudes is that grown by
        `case_wall_thickness + pcb_clearance` on every side, so 185.3 x 132.3.

        ⚠️ It is read from the recorded `fit.case_mm` and NOT from the drawn
        outline, because the drawn one is fitted to an even bezel -- so a revert
        to the bare PCB edge would be evened out too and would measure the same.
        The size before that fit is the only place the two still differ.
        """
        raw = json.loads(bo.BOARD_FILE.read_text(encoding="utf-8"))
        for half in raw["halves"]:
            got = half["fit"]["case_mm"]
            for value, want, axis in ((got[0], 185.30, "width"),
                                      (got[1], 132.30, "height")):
                self.assertAlmostEqual(value, want, delta=0.05,
                                       msg="%s case %s is %.2f mm, expected %.2f"
                                       % (half["side"], axis, value, want))

    def test_no_key_strays_onto_the_other_half(self):
        other = {"left": "right", "right": "left"}
        for name, k in self.keys.items():
            side = "left" if k["row"] in LEFT_ROWS else "right"
            cx = k["x"] + k["w"] / 2.0
            cy = k["y"] + k["h"] / 2.0
            self.assertFalse(inside(self.poly[other[side]], (cx, cy)),
                             "key %s sits on the %s board" % (name, other[side]))


class StatusDisplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.board = bo.load()
        if cls.board is None:
            raise unittest.SkipTest("no board outline shipped")
        cls.by_side = {h.side: h for h in cls.board.halves}

    def test_each_half_carries_one_status_panel(self):
        for side, half in self.by_side.items():
            self.assertEqual(1, len(half.displays), "%s half" % side)

    def test_the_two_panels_are_mirrored_about_the_layout_centre(self):
        """⚠️ A delta, not `places=3`: the panel is sized from the free corner it
        sits in, and the two boards are not exact mirrors (their Edge.Cuts differ by
        ~0.1 mm) while the corner search is on a 0.05U grid. 0.03U is a tenth of the
        bezel -- far below anything visible, and far below a real placement error.
        """
        left = self.by_side["left"].displays[0]
        right = self.by_side["right"].displays[0]
        self.assertAlmostEqual(left.cy, right.cy, delta=0.03)
        self.assertAlmostEqual(left.w, right.w, delta=0.03)
        # The KLE's centre line: the two boards are mirror images, so the
        # panels must be equidistant from it. A one-sided placement mistake
        # moves exactly one of them.
        xs = [k["x"] for k in parse_kle(json.loads(KLE.read_text(encoding="utf-8")))[2].values()]
        widths = [k["x"] + k["w"] for k in parse_kle(json.loads(KLE.read_text(encoding="utf-8")))[2].values()]
        centre = (min(xs) + max(widths)) / 2.0
        self.assertAlmostEqual(centre - left.cx, right.cx - centre, delta=0.03)

    def test_the_screen_has_NO_side_bezel_but_keeps_its_vertical_one(self):
        """The screen runs the full width of the glass and meets the housing; glass
        shows only above and below.

        ⚠️ That drops the screen's 2:1 aspect, deliberately -- it is the ONE thing
        here that is not the module's own proportion. The vertical glass is checked
        as a RATIO rather than in mm, because the panel is scaled to its corner and
        everything except the side bezel is left as the uniform fit put it: 8.4 of
        the module's 19.26 mm, whatever the scale.
        """
        want = (PANEL_H_MM - ACTIVE_H_MM) / PANEL_H_MM
        for side, half in self.by_side.items():
            for d in half.displays:
                self.assertAlmostEqual(d.w, d.aw, delta=1e-4,
                                       msg="%s panel has a side bezel" % side)
                self.assertAlmostEqual(
                    (d.h - d.ah) / d.h, want, delta=0.01,
                    msg="%s panel's glass is %.1f%% of its height, expected %.1f%%"
                        % (side, (d.h - d.ah) / d.h * 100.0, want * 100.0))

    def test_a_panel_TOUCHES_the_case_edge_beside_it(self):
        """It is grown to span its corner, so its inner edge meets the outline.

        Only that edge -- the one facing the layout's centre line -- has a wall to
        meet; the other stops one clearance short of a keycap. `GRID_U` is the corner
        search's own step, so this is "touching" to the resolution the corner was
        measured at.
        """
        for side, half in self.by_side.items():
            for d in half.displays:
                x, y, w, h = d.rect
                inner = x + w if side == "left" else x
                gaps = [edge_distance(half.outline, (inner, y + h * t))
                        for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
                self.assertLessEqual(min(gaps), GRID_U,
                                     "%s panel's inner edge is %.3fU short of the case"
                                     % (side, min(gaps)))

    def test_a_panel_HANGS_from_the_top_of_its_corner(self):
        """Not centred in it -- the corner runs all the way down to the thumb
        cluster, so centring drops the panel below the top key row and it reads as
        having slipped.

        Measured as the case above the panel at its TIGHTEST point across the width,
        because the case top slopes: 0.28U at the corner end, 0.51U at the centre.
        Top-hung gives 0.28-0.36U and centred gives 0.52U, so one bound separates
        them, and the lower bound is a real clearance rather than a restatement of
        the exporter's own sampling.
        """
        for side, half in self.by_side.items():
            for d in half.displays:
                x, y, w, _h = d.rect
                gaps = [y - t for t in (boundary_y_at(half.outline, x + w * f / 40.0)
                                        for f in range(41)) if t is not None]
                self.assertTrue(gaps, "%s: no case boundary above the panel" % side)
                self.assertGreaterEqual(min(gaps), 0.25,
                                        "%s panel has only %.3fU of case above it"
                                        % (side, min(gaps)))
                self.assertLessEqual(min(gaps), 0.45,
                                     "%s panel has %.3fU of case above it -- it has "
                                     "slipped down its corner" % (side, min(gaps)))

    def test_a_panel_STAYS_inside_the_case(self):
        """⚠️ With a tolerance, and the tolerance is the point: the panel is grown
        until its inner edge MEETS the outline, so that edge lies exactly on the
        boundary and a ray-cast containment test answers arbitrarily there. Anything
        reported outside must therefore be on the line, not past it."""
        for side, half in self.by_side.items():
            for d in half.displays:
                x, y, w, h = d.rect
                for corner in ((x, y), (x + w, y), (x + w, y + h), (x, y + h)):
                    if inside(half.outline, corner):
                        continue
                    off = edge_distance(half.outline, corner)
                    self.assertLessEqual(off, 1e-3,   # the JSON rounds to 4 dp
                                         "%s panel corner %s is %.4fU outside the case"
                                         % (side, tuple(round(c, 3) for c in corner), off))

    def test_a_panel_does_not_overlap_any_key(self):
        for side, half in self.by_side.items():
            rows = LEFT_ROWS if side == "left" else range(5, 10)
            for d in half.displays:
                dx, dy, dw, dh = d.rect
                for name, k in parse_kle(json.loads(KLE.read_text(encoding="utf-8")))[2].items():
                    if k["row"] not in rows:
                        continue
                    xs = [c[0] for c in key_corners(k)]
                    ys = [c[1] for c in key_corners(k)]
                    overlap = (min(xs) < dx + dw and max(xs) > dx
                               and min(ys) < dy + dh and max(ys) > dy)
                    self.assertFalse(overlap, "the %s status panel covers key %s"
                                     % (side, name))


if __name__ == "__main__":
    unittest.main()


class ExportIsCurrentTest(unittest.TestCase):
    """The shipped JSON still matches what the boards say.

    ⚠️ This repo has been bitten by a generator whose input path died and whose
    output then rotted for months with nothing failing (`layer_names.yaml`).
    The remedy there was to stop generating; here the input is a separate
    hardware repo, so instead the generator carries `--check` and this runs it.
    It SKIPS without a `PolyKybd` checkout, which is the normal case on a host
    install -- so it guards the developer who edits the boards, which is the
    only person who can make it stale.
    """

    def test_the_shipped_outline_matches_the_boards(self):
        import subprocess
        import sys as _sys

        root = pathlib.Path(__file__).resolve().parents[2]
        script = root / "scripts" / "export_board_outline.py"
        hardware = root.parent / "PolyKybd"
        if not (hardware / "poly_kybd").is_dir():
            raise unittest.SkipTest("no PolyKybd checkout beside this repo")
        res = subprocess.run([_sys.executable, str(script), "--check"],
                             capture_output=True, text=True, cwd=str(root))
        self.assertEqual(0, res.returncode,
                         "%s\n%s\nRe-run: python scripts/export_board_outline.py"
                         % (res.stdout, res.stderr))
