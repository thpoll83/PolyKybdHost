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
import pathlib
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polyhost import _version
from polyhost.gui.layout_dialog import qmk_keycode_helper as qh
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


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"host      : {_version.__version__}  protocol {_version.__protocol__}")
    print(f"host repo : {_git(here, 'log', '-1', '--format=%h %cs %s') or here}")

    p = KeycapPreview()
    if not p._load():
        print(f"\nPREVIEWS UNAVAILABLE: {p.reason}")
        return 1
    pk = p._fw_dir
    print(f"firmware  : {pk}")
    print(f"            {_git(pk, 'log', '-1', '--format=%h %cs %s') or '(not a git checkout)'}")
    print(f"legends   : {len(p._known)} known tokens"
          f"{'' if p._lang_ok else '  [no workbook: letters fall back to text]'}")
    print(f"runtime   : {'ok' if p._runtime and p._runtime.usable else 'unavailable'}"
          f"{'' if not p._runtime else '  ' + (p._runtime.reason or '')}")

    print("\nlayer enum (this checkout vs the one this host expects)")
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
                print(f"  {tag:<10} not in this checkout's enum")
                continue
            tok = p._layer_token(base + idx)
            print(f"  {tag:<10} kc={base + idx:#06x} -> {str(tok):<16}"
                  f" {'legend' if tok in p._known else 'NO LEGEND'}")

    print("\nbrightness legends (moons = a checkout from before 2026-08-25)")
    for n in BRIGHTNESS:
        expr = (p._static.get(n) or "").strip()
        print(f"  {n:<10} {expr[:58] or 'NO LEGEND'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
