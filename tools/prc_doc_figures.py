"""Figures for the PRC section of the docs site (reference/hid-protocol).

Writes three SVGs, every number taken from the real table and encoder:

- ``prc-stencil.svg``: the 10 neighbours that predict a pixel.
- ``prc-square-costs.svg``: a solid 10 x 10 square, each pixel labelled with
  its code length in bits.
- ``prc-quick-open-costs.svg``: VS Code's Quick Open icon, each pixel coloured
  by its code length, with three pixels called out.

    python tools/prc_doc_figures.py ../polykybd-docs/src/assets/reference

The figures draw their own dark background, so they read the same in the
site's light and dark themes.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from polyhost.util import prc_codec  # noqa: E402

BG = "#15171c"
GRID = "#2c3038"
TEXT = "#e8e8e8"
MUTED = "#9aa0aa"
ACCENT = "#ff8c00"
FONT = 'font-family="Inter, Helvetica, Arial, sans-serif"'

# Cost colour scale, cheap to expensive.
STOPS = [(0.0, (27, 31, 59)), (0.35, (40, 90, 190)), (0.7, (242, 193, 78)), (1.0, (228, 87, 46))]
COST_MIN, COST_MAX = 0.01, 6.0


def cost_colour(bits: float) -> str:
    t = (math.log10(max(bits, COST_MIN)) - math.log10(COST_MIN)) / (math.log10(COST_MAX) - math.log10(COST_MIN))
    t = min(max(t, 0.0), 1.0)
    for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:]):
        if t <= t1:
            f = (t - t0) / (t1 - t0)
            return "#%02x%02x%02x" % tuple(round(a + (b - a) * f) for a, b in zip(c0, c1))
    return "#%02x%02x%02x" % STOPS[-1][1]


def costs(roi):
    """Per-pixel code length (bits) and P(set), as 2-D lists, for a ROI coded with table v1."""
    tbl = prc_codec.table()
    h, w = len(roi), len(roi[0])
    ctx = prc_codec.contexts(roi)
    cost, pset = [], []
    for y in range(h):
        crow, prow = [], []
        for x in range(w):
            p0 = tbl[ctx[y * w + x]] / 256
            is_set = bool(roi[y][x])
            crow.append(-math.log2(1 - p0 if is_set else p0))
            prow.append(1 - p0)
        cost.append(crow)
        pset.append(prow)
    return cost, pset


def svg(width, height, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">\n'
            f'<rect width="{width}" height="{height}" fill="{BG}"/>\n{body}</svg>\n')


def legend(x, y, width):
    """Horizontal code-length scale with tick labels."""
    parts = [f'<defs><linearGradient id="scale">']
    for t, c in STOPS:
        parts.append(f'<stop offset="{t}" stop-color="rgb{c}"/>')
    parts.append('</linearGradient></defs>')
    parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="12" fill="url(#scale)"/>')
    for bits in (0.01, 0.1, 1, 6):
        t = (math.log10(bits) - math.log10(COST_MIN)) / (math.log10(COST_MAX) - math.log10(COST_MIN))
        tx = x + t * width
        parts.append(f'<line x1="{tx:.1f}" y1="{y + 12}" x2="{tx:.1f}" y2="{y + 17}" stroke="{MUTED}"/>')
        parts.append(f'<text x="{tx:.1f}" y="{y + 30}" fill="{MUTED}" font-size="12" text-anchor="middle" {FONT}>'
                     f'{bits:g} bit{"s" if bits != 1 else ""}</text>')
    parts.append(f'<text x="{x}" y="{y - 8}" fill="{MUTED}" font-size="12" {FONT}>'
                 f'code length per pixel (bits): predicted = short, mispredicted = long</text>')
    return "\n".join(parts)


def stencil():
    c = 64
    ox, oy = 40, 50
    known = {(dy, dx): i + 1 for i, (dy, dx) in enumerate(prc_codec.TEMPLATE)}
    parts = [f'<text x="{ox}" y="30" fill="{TEXT}" font-size="15" {FONT}>'
             f'Causal context template: the 10 pixels that predict pixel ?</text>']
    for dy in range(-2, 1):
        for dx in range(-3, 4):
            x, y = ox + (dx + 3) * c, oy + (dy + 2) * c
            if (dy, dx) in known:
                parts.append(f'<rect x="{x}" y="{y}" width="{c}" height="{c}" fill="#284f9e" stroke="{GRID}" stroke-width="2"/>')
                parts.append(f'<text x="{x + c / 2}" y="{y + c / 2 + 7}" fill="{TEXT}" font-size="20" '
                             f'text-anchor="middle" {FONT}>{known[(dy, dx)]}</text>')
            elif (dy, dx) == (0, 0):
                parts.append(f'<rect x="{x}" y="{y}" width="{c}" height="{c}" fill="{BG}" stroke="{ACCENT}" stroke-width="3"/>')
                parts.append(f'<text x="{x + c / 2}" y="{y + c / 2 + 9}" fill="{ACCENT}" font-size="26" '
                             f'text-anchor="middle" {FONT}>?</text>')
            else:
                fill = "#1f2229" if dy < 0 else BG
                parts.append(f'<rect x="{x}" y="{y}" width="{c}" height="{c}" fill="{fill}" stroke="{GRID}" stroke-width="2"/>')
    ly = oy + 3 * c + 30
    chips = [("#284f9e", "decoded and used: the 10 values form the context 0-1023, neighbour 1 is the top bit"),
             ("#1f2229", "decoded, not used"),
             (BG, "not decoded yet")]
    for i, (fill, label) in enumerate(chips):
        y = ly + i * 22
        parts.append(f'<rect x="{ox}" y="{y - 12}" width="14" height="14" fill="{fill}" stroke="{GRID}"/>')
        parts.append(f'<text x="{ox + 22}" y="{y}" fill="{MUTED}" font-size="13" {FONT}>{label}</text>')
    y = ly + len(chips) * 22 + 6
    parts.append(f'<text x="{ox}" y="{y}" fill="{TEXT}" font-size="13" {FONT}>'
                 f'The table maps each context to P(clear). Pixels outside the ROI count as clear.</text>')
    return svg(ox * 2 + 7 * c + 80, y + 20, "\n".join(parts))


def square():
    roi = [[1] * 10 for _ in range(10)]
    cost, _ = costs(roi)
    total = sum(map(sum, cost))
    payload = len(prc_codec.encode(roi))
    c = 52
    ox, oy = 30, 50
    parts = [f'<text x="{ox}" y="30" fill="{TEXT}" font-size="15" {FONT}>'
             f'A solid 10 × 10 square: code length of each pixel (bits)</text>']
    for y in range(10):
        for x in range(10):
            px, py = ox + x * c, oy + y * c
            b = cost[y][x]
            parts.append(f'<rect x="{px}" y="{py}" width="{c}" height="{c}" fill="{cost_colour(b)}" stroke="{BG}" stroke-width="2"/>')
            label = f"{b:.1f}" if b >= 1 else (f"{b:.2f}".lstrip("0") if b >= 0.01 else f"{b:.3f}".lstrip("0"))
            parts.append(f'<text x="{px + c / 2}" y="{py + c / 2 + 5}" fill="#ffffff" font-size="14" '
                         f'text-anchor="middle" {FONT}>{label}</text>')
    by = oy + 10 * c + 30
    parts.append(f'<text x="{ox}" y="{by}" fill="{TEXT}" font-size="14" {FONT}>'
                 f'{total:.1f} bits of information for 100 pixels. Payload {payload} bytes; uncoded, 13.</text>')
    parts.append(legend(ox, by + 40, 10 * c))
    return svg(ox * 2 + 10 * c, by + 90, "\n".join(parts))


def quick_open():
    import numpy as np
    from polyhost.device.device_settings import DeviceSettings
    from polyhost.device.im_converter import ImageConverter
    from polyhost.device.keys import KeyCode, Modifier
    conv = ImageConverter(DeviceSettings())
    if not conv.open(os.path.join(ROOT, "polyhost", "res", "overlays", "vscode_template.mods.png")):
        raise SystemExit("cannot read the VS Code template")
    ov = conv.extract_overlays(Modifier.CTRL)[KeyCode.KC_P.value]
    img = np.unpackbits(np.frombuffer(ov.all_bytes, dtype=np.uint8)).reshape(40, 72).astype(bool)
    top, left, h, w = prc_codec.roi_box(img)
    roi = img[top:top + h, left:left + w].astype(int).tolist()
    cost, pset = costs(roi)
    total = sum(map(sum, cost))
    payload = len(prc_codec.encode(roi))
    flat = sorted((cost[y][x], y, x) for y in range(h) for x in range(w))
    cheap = [v for v, _, _ in flat if v < 0.1]
    dear = [v for v, _, _ in flat if v >= 1]

    # Three call-outs: the longest set pixel, the longest clear pixel, a short set pixel.
    def first(pred):
        return next((y, x) for v, y, x in reversed(flat) if pred(y, x, v))
    a = first(lambda y, x, v: roi[y][x])
    b = first(lambda y, x, v: not roi[y][x])
    cy, cx = min(((y, x) for v, y, x in flat if roi[y][x] and v < 0.05), key=lambda p: abs(p[0] - h // 2))
    calls = [("A", a), ("B", b), ("C", (cy, cx))]

    c = 18
    ox, oy = 30, 50
    parts = [f'<text x="{ox}" y="30" fill="{TEXT}" font-size="15" {FONT}>'
             f'VS Code Quick Open ({w} × {h} px ROI): code length of each pixel</text>']
    for y in range(h):
        for x in range(w):
            px, py = ox + x * c, oy + y * c
            parts.append(f'<rect x="{px}" y="{py}" width="{c}" height="{c}" fill="{cost_colour(cost[y][x])}"/>')
            if roi[y][x]:
                parts.append(f'<rect x="{px + 4}" y="{py + 4}" width="{c - 8}" height="{c - 8}" fill="none" '
                             f'stroke="#ffffff" stroke-width="1.5"/>')
    tx = ox + w * c + 30
    ty = oy + 10
    for name, (y, x) in calls:
        px, py = ox + x * c + c / 2, oy + y * c + c / 2
        parts.append(f'<circle cx="{px}" cy="{py}" r="{c * 0.9}" fill="none" stroke="{ACCENT}" stroke-width="2.5"/>')
        parts.append(f'<rect x="{px + c - 4}" y="{py - c - 16}" width="20" height="20" rx="3" fill="{BG}" stroke="{ACCENT}"/>')
        parts.append(f'<text x="{px + c + 6}" y="{py - c}" fill="{ACCENT}" font-size="15" font-weight="bold" '
                     f'text-anchor="middle" {FONT}>{name}</text>')
    for name, (y, x) in calls:
        what = "set" if roi[y][x] else "clear"
        lines = [f'{name}: {what}, table gave P(set) = {100 * pset[y][x]:.1f}%',
                 f'   code length {cost[y][x]:.2f} bits']
        for i, line in enumerate(lines):
            parts.append(f'<text x="{tx}" y="{ty + i * 18}" fill="{ACCENT if i == 0 else TEXT}" font-size="14" '
                         f'xml:space="preserve" {FONT}>{line}</text>')
        ty += 52
    stats = [f'{h * w} pixels, {total:.1f} bits of information',
             f'payload {payload} bytes (+ 6-byte header)',
             f'{len(cheap)} pixels ({100 * len(cheap) / (h * w):.0f}%) code &lt; 0.1 bit: {sum(cheap):.0f} bits in total',
             f'{len(dear)} pixels ({100 * len(dear) / (h * w):.0f}%) code ≥ 1 bit: {100 * sum(dear) / total:.0f}% of all bits',
             'white outline = set pixel']
    for i, line in enumerate(stats):
        parts.append(f'<text x="{tx}" y="{ty + 10 + i * 20}" fill="{TEXT if i < 4 else MUTED}" font-size="14" {FONT}>{line}</text>')
    by = oy + h * c + 40
    parts.append(legend(ox, by, 360))
    return svg(tx + 330, by + 45, "\n".join(parts))


def main(argv=None) -> int:
    out = (argv or sys.argv[1:] or ["."])[0]
    os.makedirs(out, exist_ok=True)
    for name, make in (("prc-stencil.svg", stencil), ("prc-square-costs.svg", square),
                       ("prc-quick-open-costs.svg", quick_open)):
        path = os.path.join(out, name)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(make())
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
