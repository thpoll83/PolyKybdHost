"""Where the host finds files in a qmk_firmware checkout.

The previews, the macro label meter and several tools read firmware sources and
font headers from a checkout beside this repo (``../qmk_firmware``). In 2026-11 the
firmware moved its sources out of the ``keyboards/polykybd`` root into folders, and
``base/fonts`` became ``fonts``. A host of any version can be run against a
checkout of either layout, so every lookup here tries the current path first and
then the path before the move.
"""
from __future__ import annotations

import os

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Current path -> path before the 2026-11 move, for the files the host reads.
_BEFORE_MOVE = {
    "keymap/poly_keymap.c": "poly_keymap.c",
    "keymap/keycode_helper.c": "keycode_helper.c",
    "keymap/keycode_helper.h": "keycode_helper.h",
    "keymap/lang_layer.c": "lang_layer.c",
    "keymap/lang_layer.h": "lang_layer.h",
    "keymap/layer_names.c": "layer_names.c",
    "keymap/poly_combos.c": "poly_combos.c",
    "keymap/uni.h": "uni.h",
    "modes/midi_legend.c": "midi_legend.c",
    "hid/hid_com.c": "hid_com.c",
    "system/state.h": "state.h",
}

# The font headers: "fonts" now, "base/fonts" before the move. The generator
# directory "fonts" exists in both layouts, so a header inside it decides.
_FONT_DIRS = ("fonts", os.path.join("base", "fonts"))
_FONT_MARKER = "gfxfont.h"


def checkout_dir() -> str:
    """``<qmk_firmware>/keyboards/polykybd`` beside this repo (it may not exist)."""
    return os.path.join(os.path.dirname(_REPO), "qmk_firmware", "keyboards", "polykybd")


def font_dir(pk: str | os.PathLike | None = None) -> str:
    """The font header directory of the checkout ``pk`` (default: beside this repo)."""
    pk = os.fspath(pk) if pk is not None else checkout_dir()
    for rel in _FONT_DIRS:
        cand = os.path.join(pk, rel)
        if os.path.isfile(os.path.join(cand, _FONT_MARKER)):
            return cand
    return os.path.join(pk, _FONT_DIRS[0])


def fw_file(pk: str | os.PathLike, rel: str) -> str:
    """Path of firmware file ``rel`` (current layout) inside the checkout ``pk``.

    Returns the path before the move when only that one exists, else the current
    path, so a missing file is reported under its current name.
    """
    pk = os.fspath(pk)
    cur = os.path.join(pk, rel)
    old = _BEFORE_MOVE.get(rel)
    if old and not os.path.exists(cur) and os.path.exists(os.path.join(pk, old)):
        return os.path.join(pk, old)
    return cur
