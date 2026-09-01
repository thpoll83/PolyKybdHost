#!/usr/bin/env python3
"""Report what the keymap-editor key previews are actually reading.

The previews have no legends of their own: they parse the FIRMWARE SOURCE from a
`qmk_firmware` checkout beside this repo. So "the icons are the old ones" and "that
key has no preview" are both questions about which checkout, at which commit -- and
until this script existed the only way to answer them was to go and look at someone
else's disk. Run it and paste the output.

    python tools/preview_doctor.py
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polyhost import _version
from polyhost.gui.layout_dialog import qmk_keycode_helper as qh
from polyhost.services import preview_data as pdata
from polyhost.gui.layout_dialog.keycap_preview import KeycapPreview

# The layer keys the shipped keymap binds on the base layer, by QMK range base.
LAYER_KEYS = (("QK_MOMENTARY", 0x5220, ("FL", "NL", "ADDLANG1")),
              ("QK_TO", 0x5200, ("EMJ", "SL")))
BRIGHTNESS = ("KC_DMIN", "KC_D1Q", "KC_DHLF", "KC_D3Q", "KC_DMAX",
              "KC_DDIM", "KC_DBRI", "KC_DAUTO")


def _git(path, *args):
    try:
        return subprocess.run(["git", "-C", path, *args], capture_output=True,
                              text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _cp_family(cps):
    """Name the glyph family a brightness legend draws from.

    ⚠️ This is the ONE-LINE tell for a stale data source, and it is a better answer
    than printing the C expression: the brightness keys became a sun family on
    2026-08-25, and before that `keycode_helper.c` returned `PRIVATE_DISP_*`, which
    are MOON emoji. So "moons" means the data predates that commit, full stop.
    """
    if not cps:
        return "NO LEGEND"
    if any(0x1F311 <= c <= 0x1F318 for c in cps):
        return "MOONS  <- data predates 2026-08-25"
    if any(0x80 <= c <= 0x9F for c in cps):
        return "suns (IconsFont C1)"
    return "other"


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"host      : {_version.__version__}  protocol {_version.__protocol__}")
    print(f"host repo : {_git(here, 'log', '-1', '--format=%h %cs %s') or here}")

    p = KeycapPreview()
    if not p._load():
        print(f"\nPREVIEWS UNAVAILABLE: {p.reason}")
        return 1

    # The headline: WHICH data the keycaps are drawn from. Everything below is a
    # property of that source, and reading it as a property of the other one is
    # what cost three rounds of guessing before this tool existed.
    print(f"source    : {p.source}  (firmware {p._fw_version or 'unknown'})")
    if p.source == "shipped":
        print(f"            {pdata.PREVIEW_DIR}")
        if p._checkout_unused:
            print("            a firmware checkout is present but is not newer, "
                  "so it is not used")
    else:
        pk = p._fw_dir
        print(f"            {pk}")
        print(f"            "
              f"{_git(pk, 'log', '-1', '--format=%h %cs %s') or '(not a git checkout)'}")
    print(f"legends   : {len(p._known)} known tokens"
          f"{'' if p._lang_ok else '  [no language table: letters fall back to text]'}")

    print("\nlayer enum (this source vs the one this host expects)")
    derived = p._layer_tags
    for i in sorted(set(derived) | set(qh.LAYER_TAGS)):
        mine, ship = derived.get(i, "-"), qh.LAYER_TAGS.get(i, "-")
        print(f"  {i:>2}  {mine:<10} {'' if mine == ship else f'!= {ship}'}")
    print(f"  -> {p._tag_drift or 'in step'}")

    print("\nlayer keys")
    for _, base, tags in LAYER_KEYS:
        for tag in tags:
            idx = next((i for i, t in derived.items() if t == tag), None)
            if idx is None:
                print(f"  {tag:<10} not in this source's enum")
                continue
            tok = p._layer_token(base + idx)
            print(f"  {tag:<10} kc={base + idx:#06x} -> {str(tok):<16}"
                  f" {'legend' if tok in p._known else 'NO LEGEND'}")

    print("\nbrightness legends")
    for n in BRIGHTNESS:
        print(f"  {n:<10} {_cp_family(p._legends.get(n))}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        # This exists to be piped into `head` / `tail` / a paste buffer, and a
        # traceback there is one more confusing thing to report.
        os._exit(0)
