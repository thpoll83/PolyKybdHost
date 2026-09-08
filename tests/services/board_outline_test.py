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

    def test_no_key_hangs_far_over_the_edge(self):
        """Corners get a tolerance, because a few genuinely do overhang.

        The KLE draws the thumb clusters in whole key units where the board
        rotates them by measured angles, so six corners of the four outermost
        thumbs sit outside the real edge -- worst 0.10U (1.9 mm), measured. The
        bound is set just above that: it still fails on a wrong offset, which
        moves every key at once and by far more.
        """
        for name, k in self.keys.items():
            side = "left" if k["row"] in LEFT_ROWS else "right"
            for corner in key_corners(k):
                if inside(self.poly[side], corner):
                    continue
                over = edge_distance(self.poly[side], corner)
                self.assertLessEqual(over, 0.15,
                                     "key %s corner %s hangs %.3fU off the %s board"
                                     % (name, tuple(round(c, 2) for c in corner), over, side))

    def test_the_board_HUGS_the_keys_on_every_side(self):
        """The check the containment tests cannot make on their own.

        A board that is merely BIG enough contains every key however it is
        translated -- measured, shifting both outlines 0.25U inward still
        passes containment, because the inner edge has that much slack. A real
        plate hugs its keys, so the margin from the outermost key to the edge
        is bounded on both ends: measured 0.10U to 0.38U on the shipped
        boards, and a translation pushes one side out of that immediately.
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
                self.assertGreaterEqual(margin, -0.05,
                                        "%s board: keys run %.3fU past the %s edge"
                                        % (half.side, -margin, side))
                self.assertLessEqual(margin, 0.45,
                                     "%s board: %.3fU of slack at the %s edge -- the "
                                     "outline is not where the keys are"
                                     % (half.side, margin, side))

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
        left = self.by_side["left"].displays[0]
        right = self.by_side["right"].displays[0]
        self.assertAlmostEqual(left.cy, right.cy, places=2)
        self.assertAlmostEqual(left.w, right.w, places=3)
        # The KLE's centre line: the two boards are mirror images, so the
        # panels must be equidistant from it. A one-sided placement mistake
        # moves exactly one of them.
        xs = [k["x"] for k in parse_kle(json.loads(KLE.read_text(encoding="utf-8")))[2].values()]
        widths = [k["x"] + k["w"] for k in parse_kle(json.loads(KLE.read_text(encoding="utf-8")))[2].values()]
        centre = (min(xs) + max(widths)) / 2.0
        self.assertAlmostEqual(centre - left.cx, right.cx - centre, places=2)

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
