#!/usr/bin/env python3
"""Freeze the FIRMWARE's status-panel renderer as a fixture the host is pinned to.

`polyhost/services/status_screen.py` is a port of
`qmk_firmware/keyboards/polykybd/tools/status_oled_preview.py`, and a port drifts.
This runs the firmware tool and writes the lit pixels it produces, so
`tests/services/status_screen_test.py` can compare the port against them WITHOUT a
firmware checkout — which is the only way that pin holds on a machine that has none.

Re-run it whenever `split72/status_oled.c` moves a row:

    python scripts/gen_status_panel_golden.py [--firmware <path>] [--check]

⚠️ The fixture is only as good as the tree it came from, so it records the firmware
version it was taken at; `--check` reports drift instead of writing.
"""
import argparse
import base64
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "tests" / "services" / "status_panel_golden.json"

#: The cases the fixture covers: both panels, both RGB states, plus one case whose
#: values do NOT saturate.
#:
#: ⚠️ That last pair is not padding — it is the whole difference between a fixture and
#: a fixture that CHECKS something. The firmware's own defaults are `brightness=50`
#: (= FULL_BRIGHT, so every gauge segment is lit and no unlit one exists to keep its
#: 1px foot) and `sat=255` / `val=100` (whose percentages round the same with and
#: without the `+127`). Measured: three mutations of this port — dropping the unlit
#: segment's foot, dropping the percent rounding, and swapping the gauge's fill — all
#: ESCAPED against the saturating cases and are caught by these. Pick fixture values
#: away from the boundary, or the pin only proves the easy half.
#:
#: ⚠️ The LAYER is always 0, because that is what `build_panel` hardcodes — it takes
#: no layer argument. Re-drawing the digit here to cover a hex letter was tried and
#: dropped: it means subtracting the '0' pixels and adding another glyph's, which is a
#: transformation of the fixture rather than the tool's own output, and a fixture that
#: is not verbatim cannot pin anything. The digit is covered host-side instead, by
#: drawing it through the same face at the same origin.
RGB_DEFAULT = (128, 255, 100, 80, 5, "Rainbow")
RGB_MID = (30, 140, 180, 190, 7, "Splash2")     # non-saturating S/V; a "2" name too

CASES = [
    {"side": "L", "layout": "Qwerty", "rgb": True},
    {"side": "R", "layout": "Qwerty", "rgb": True},
    {"side": "L", "layout": "Qwerty", "rgb": False},
    {"side": "R", "layout": "Qwerty", "rgb": False},
    {"side": "L", "layout": "Colemak DH", "rgb": True, "brightness": 23,
     "hsv": "mid", "lang": "mn-MN", "wpm": 137},
    {"side": "R", "layout": "Colemak DH", "rgb": True, "brightness": 23,
     "hsv": "mid", "lang": "mn-MN", "wpm": 137},
]

PANEL_W, PANEL_H = 128, 64


def pack(pts):
    """The panel as a row-major 1-bit bitmap, base64.

    A list of coordinate pairs is 200 KB of JSON for five panels; this is 1.4 KB each
    and diffs as one line per case, which is what a frozen artifact should look like.
    """
    buf = bytearray(PANEL_H * ((PANEL_W + 7) // 8))
    stride = (PANEL_W + 7) // 8
    for x, y in pts:
        if 0 <= x < PANEL_W and 0 <= y < PANEL_H:
            buf[y * stride + (x >> 3)] |= 0x80 >> (x & 7)
    return base64.b64encode(bytes(buf)).decode("ascii")


def unpack(b64):
    """The inverse, for the test that compares against a freshly rendered panel."""
    buf = base64.b64decode(b64)
    stride = (PANEL_W + 7) // 8
    return {(x, y)
            for y in range(PANEL_H) for x in range(PANEL_W)
            if buf[y * stride + (x >> 3)] & (0x80 >> (x & 7))}


def firmware_dir(explicit=None):
    if explicit:
        return pathlib.Path(explicit)
    here = HERE.parent.parent
    return here / "qmk_firmware" / "keyboards" / "polykybd"


def firmware_version(pk: pathlib.Path) -> str:
    m = re.search(r'#define\s+FW_VERSION\s+"([^"]+)"',
                  (pk / "config.h").read_text(encoding="utf-8", errors="ignore"))
    return m.group(1) if m else "unknown"


def build(pk: pathlib.Path):
    """Drive the firmware tool. It resolves its font dir relative to ITS OWN file, so
    only sys.path matters -- but it also expects to be run from keyboards/polykybd."""
    sys.path.insert(0, str(pk / "tools"))
    cwd = os.getcwd()
    os.chdir(pk)
    try:
        import status_oled_preview as sop
        disp, small, icons, tiny, globe = sop.load_fonts()
        out = []
        for c in CASES:
            rgb = None
            if c["rgb"]:
                rgb = RGB_MID if c.get("hsv") == "mid" else RGB_DEFAULT
            pts = sop.build_panel(c["side"], disp, small, icons, tiny, globe,
                                  brightness=c.get("brightness", 50), rgb=rgb,
                                  lang=c.get("lang", "en-US"),
                                  wpm=c.get("wpm", 0), layout=c["layout"])
            out.append({**c, "bitmap": pack(pts)})
        return out
    finally:
        os.chdir(cwd)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--firmware", help="path to keyboards/polykybd in a checkout")
    ap.add_argument("--check", action="store_true",
                    help="report drift instead of writing")
    args = ap.parse_args()

    pk = firmware_dir(args.firmware)
    if not (pk / "tools" / "status_oled_preview.py").exists():
        print("no firmware checkout at %s" % pk)
        return 2

    data = {"firmware": firmware_version(pk),
            "source": "keyboards/polykybd/tools/status_oled_preview.py",
            "note": ("Generated by scripts/gen_status_panel_golden.py -- do not "
                     "hand-edit. Pins polyhost/services/status_screen.py to what "
                     "the firmware's own preview tool draws."),
            "cases": build(pk)}
    text = json.dumps(data, indent=1, sort_keys=True) + "\n"

    if args.check:
        if not OUT.exists():
            print("MISSING %s" % OUT)
            return 1
        old = json.loads(OUT.read_text(encoding="utf-8"))
        new = json.loads(text)
        old.pop("firmware", None)
        new.pop("firmware", None)
        if old != new:
            print("STALE %s -- the firmware panel has moved" % OUT)
            return 1
        print("current: %s" % OUT)
        return 0

    OUT.write_text(text, encoding="utf-8")
    print("wrote %s (%d cases, firmware %s)"
          % (OUT, len(data["cases"]), data["firmware"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
