"""Rasterise a single-colour SVG icon without a native cairo.

⚠️ THIS EXISTS BECAUSE `cairosvg` DOES NOT INSTALL ON WINDOWS. It depends on
`cairocffi`, which ships **no Windows wheel and no bundled library** -- it
dlopens `libcairo-2.dll` at runtime, which is not present on a stock Windows
Python. So on the platform most of these users are on, `import cairosvg` raises
and every program icon silently fails to draw. Checked on PyPI, not assumed:
both packages publish `py3-none-any` wheels only.

What this uses instead is already a declared runtime dependency and DOES ship a
Windows binary wheel with FreeType inside it: `freetype-py`, driven through
`fontTools.pens.freetypePen`. FreeType fills with the nonzero winding rule,
which is SVG's default and what these icons are drawn for -- measured, none of
them sets `fill-rule`.

The scope is deliberately narrow: the `<path>` elements of a flat, one-colour
icon on a `viewBox`. No strokes, no gradients, no groups, no transforms, no
text. That is exactly what Simple Icons and Material Design Icons are, and
anything else should keep using cairosvg.
"""

from __future__ import annotations

import math
import re

_PATH_RE = re.compile(r"<path\b[^>]*?\bd=\"([^\"]+)\"", re.S)
_VIEWBOX_RE = re.compile(r'\bviewBox="\s*([-\d.eE]+)[,\s]+([-\d.eE]+)[,\s]+'
                         r'([-\d.eE]+)[,\s]+([-\d.eE]+)', re.S)
_CMD_RE = re.compile(r"[MmZzLlHhVvCcSsQqTtAa]")
_NUM_RE = re.compile(r"[-+]?(?:[0-9]*\.[0-9]+|[0-9]+\.?)(?:[eE][-+]?[0-9]+)?")
_SEP_RE = re.compile(r"[\s,]*")

# Segments per arc/curve when flattening is needed. Arcs are converted to cubic
# beziers instead (exact enough that FreeType's own flattening takes over), so
# this only bounds how many cubics one arc becomes.
_ARC_MAX_SWEEP = math.pi / 2


def available() -> bool:
    try:
        from fontTools.pens.freetypePen import FreeTypePen  # noqa: F401
        return True
    except Exception:
        return False


class _Scanner:
    """A cursor over a path `d` string.

    ⚠️ A path is NOT a flat list of numbers and commands, which is what the
    first version assumed and what broke on two of thirteen real icons. An
    arc's `large-arc-flag` and `sweep-flag` are SINGLE CHARACTERS and may run
    straight into each other and into the next coordinate: `a1.5 1.5 0 01.5.5`
    is rx=1.5 ry=1.5 rot=0 large=0 sweep=1 x=.5 y=.5. Tokenising first reads
    `01` as one number and everything after it is garbage -- Firefox and Docker
    both failed exactly there. So the flags are read by a scanner that knows it
    is inside an arc.
    """

    def __init__(self, data: str):
        self.data = data
        self.i = 0

    def skip(self):
        self.i = _SEP_RE.match(self.data, self.i).end()

    def at_end(self) -> bool:
        self.skip()
        return self.i >= len(self.data)

    def command(self):
        self.skip()
        match = _CMD_RE.match(self.data, self.i)
        if not match:
            return None
        self.i = match.end()
        return match.group()

    def number(self):
        self.skip()
        match = _NUM_RE.match(self.data, self.i)
        if not match:
            raise ValueError(f"expected a number at {self.i}")
        self.i = match.end()
        return float(match.group())

    def numbers(self, count):
        return [self.number() for _ in range(count)]

    def flag(self) -> bool:
        self.skip()
        if self.i >= len(self.data) or self.data[self.i] not in "01":
            raise ValueError(f"expected an arc flag at {self.i}")
        value = self.data[self.i] == "1"
        self.i += 1
        return value

    def peek_is_number(self) -> bool:
        self.skip()
        return bool(_NUM_RE.match(self.data, self.i))


def _arc_to_cubics(x0, y0, rx, ry, phi, large_arc, sweep, x1, y1):
    """SVG endpoint-parameterised arc -> a list of cubic bezier segments.

    Straight out of the SVG 1.1 implementation notes (F.6.5/F.6.6), including
    the radii-too-small correction. Simple Icons uses `A` heavily -- every
    rounded corner is one -- so this is not an edge case.
    """
    if rx == 0 or ry == 0 or (x0 == x1 and y0 == y1):
        return [("L", x1, y1)]
    rx, ry = abs(rx), abs(ry)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx2, dy2 = (x0 - x1) / 2.0, (y0 - y1) / 2.0
    x1p = cos_p * dx2 + sin_p * dy2
    y1p = -sin_p * dx2 + cos_p * dy2

    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        scale = math.sqrt(lam)
        rx, ry = rx * scale, ry * scale

    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    factor = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large_arc == sweep:
        factor = -factor
    cxp, cyp = factor * rx * y1p / ry, -factor * ry * x1p / rx
    cx = cos_p * cxp - sin_p * cyp + (x0 + x1) / 2.0
    cy = sin_p * cxp + cos_p * cyp + (y0 + y1) / 2.0

    def angle(ux, uy, vx, vy):
        dot = ux * vx + uy * vy
        norm = math.hypot(ux, uy) * math.hypot(vx, vy)
        if norm == 0:
            return 0.0
        a = math.acos(max(-1.0, min(1.0, dot / norm)))
        return -a if ux * vy - uy * vx < 0 else a

    theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    delta = angle((x1p - cxp) / rx, (y1p - cyp) / ry,
                  (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    elif sweep and delta < 0:
        delta += 2 * math.pi

    steps = max(1, int(math.ceil(abs(delta) / _ARC_MAX_SWEEP)))
    step = delta / steps
    alpha = (4.0 / 3.0) * math.tan(step / 4.0)
    out = []
    theta = theta1
    px = cx + rx * math.cos(phi) * math.cos(theta) - ry * math.sin(phi) * math.sin(theta)
    py = cy + rx * math.sin(phi) * math.cos(theta) + ry * math.cos(phi) * math.sin(theta)
    for _ in range(steps):
        theta_next = theta + step
        dx_t = -rx * math.cos(phi) * math.sin(theta) - ry * math.sin(phi) * math.cos(theta)
        dy_t = -rx * math.sin(phi) * math.sin(theta) + ry * math.cos(phi) * math.cos(theta)
        ex = cx + rx * math.cos(phi) * math.cos(theta_next) - ry * math.sin(phi) * math.sin(theta_next)
        ey = cy + rx * math.sin(phi) * math.cos(theta_next) + ry * math.cos(phi) * math.sin(theta_next)
        dx_e = -rx * math.cos(phi) * math.sin(theta_next) - ry * math.sin(phi) * math.cos(theta_next)
        dy_e = -rx * math.sin(phi) * math.sin(theta_next) + ry * math.cos(phi) * math.cos(theta_next)
        out.append(("C", px + alpha * dx_t, py + alpha * dy_t,
                    ex - alpha * dx_e, ey - alpha * dy_e, ex, ey))
        theta, px, py = theta_next, ex, ey
    return out


def parse_path(data: str):
    """An SVG path `d` string as absolute ('M'|'L'|'C'|'Q'|'Z', *coords) tuples.

    Relative forms, the shorthands (H/V/S/T) and arcs are all resolved here, so
    a consumer only has to handle four commands. Malformed input stops the walk
    and returns what parsed -- a partly drawn icon beats an exception on the
    overlay path.
    """
    scan = _Scanner(data)
    out = []
    x = y = start_x = start_y = 0.0
    last_c2 = last_q = None
    command = None
    try:
        while not scan.at_end():
            found = scan.command()
            if found:
                command = found
            elif command is None:
                break
            elif command in "Mm":
                # A repeated moveto argument is an implicit LINETO, per the spec.
                command = "L" if command == "M" else "l"
            elif command in "Zz":
                break
            if command in "Zz":
                out.append(("Z",))
                x, y = start_x, start_y
                last_c2 = last_q = None
                continue

            rel = command.islower()
            upper = command.upper()
            if upper == "M":
                dx, dy = scan.numbers(2)
                x, y = (x + dx, y + dy) if rel else (dx, dy)
                start_x, start_y = x, y
                out.append(("M", x, y))
                last_c2 = last_q = None
            elif upper == "L":
                dx, dy = scan.numbers(2)
                x, y = (x + dx, y + dy) if rel else (dx, dy)
                out.append(("L", x, y))
                last_c2 = last_q = None
            elif upper == "H":
                dx = scan.number()
                x = x + dx if rel else dx
                out.append(("L", x, y))
                last_c2 = last_q = None
            elif upper == "V":
                dy = scan.number()
                y = y + dy if rel else dy
                out.append(("L", x, y))
                last_c2 = last_q = None
            elif upper in ("C", "S"):
                if upper == "C":
                    a, b, c, d, e, f = scan.numbers(6)
                    x1, y1 = (x + a, y + b) if rel else (a, b)
                else:
                    c, d, e, f = scan.numbers(4)
                    x1, y1 = (2 * x - last_c2[0], 2 * y - last_c2[1]) if last_c2 else (x, y)
                x2, y2 = (x + c, y + d) if rel else (c, d)
                ex, ey = (x + e, y + f) if rel else (e, f)
                out.append(("C", x1, y1, x2, y2, ex, ey))
                last_c2, last_q = (x2, y2), None
                x, y = ex, ey
            elif upper in ("Q", "T"):
                if upper == "Q":
                    a, b, e, f = scan.numbers(4)
                    qx, qy = (x + a, y + b) if rel else (a, b)
                else:
                    e, f = scan.numbers(2)
                    qx, qy = (2 * x - last_q[0], 2 * y - last_q[1]) if last_q else (x, y)
                ex, ey = (x + e, y + f) if rel else (e, f)
                out.append(("Q", qx, qy, ex, ey))
                last_q, last_c2 = (qx, qy), None
                x, y = ex, ey
            elif upper == "A":
                rx, ry, rot = scan.numbers(3)
                large, sweep = scan.flag(), scan.flag()
                ex, ey = scan.numbers(2)
                ax, ay = (x + ex, y + ey) if rel else (ex, ey)
                out.extend(_arc_to_cubics(x, y, rx, ry, math.radians(rot),
                                          large, sweep, ax, ay))
                x, y = ax, ay
                last_c2 = last_q = None
            else:
                break
    except ValueError:
        pass
    return out


def viewbox(text: str):
    match = _VIEWBOX_RE.search(text)
    if not match:
        return None
    x0, y0, w, h = (float(v) for v in match.groups())
    return (x0, y0, w, h) if w > 0 and h > 0 else None


def rasterise(svg_text: str, width: int, height: int):
    """An (height, width) float array of coverage 0..1, or None.

    Returns None rather than raising for anything it does not handle, so a
    caller can fall through to another rasteriser.
    """
    try:
        from fontTools.pens.freetypePen import FreeTypePen
        from fontTools.misc.transform import Transform
        import numpy as np
    except Exception:
        return None
    box = viewbox(svg_text)
    paths = _PATH_RE.findall(svg_text)
    if not box or not paths:
        return None
    x0, y0, vw, vh = box
    try:
        pen = FreeTypePen(None)
        for data in paths:
            open_contour = False
            for seg in parse_path(data):
                op = seg[0]
                if op == "M":
                    if open_contour:
                        pen.closePath()
                    pen.moveTo((seg[1], seg[2]))
                    open_contour = True
                elif not open_contour:
                    continue            # a path that starts without a moveto
                elif op == "L":
                    pen.lineTo((seg[1], seg[2]))
                elif op == "C":
                    pen.curveTo((seg[1], seg[2]), (seg[3], seg[4]), (seg[5], seg[6]))
                elif op == "Q":
                    pen.qCurveTo((seg[1], seg[2]), (seg[3], seg[4]))
                elif op == "Z":
                    pen.closePath()
                    open_contour = False
            if open_contour:
                pen.closePath()
        # ⚠️ FreeType's y runs UP and SVG's runs DOWN, so the transform flips it
        # and moves the viewBox origin to 0. Without the flip the icon renders
        # upside down, which reads as a bad parse rather than a bad transform.
        sx, sy = width / vw, height / vh
        transform = Transform(sx, 0, 0, -sy, -x0 * sx, (y0 + vh) * sy)
        array = pen.array(width=width, height=height, transform=transform)
    except Exception:
        return None
    return np.asarray(array, dtype=float)
