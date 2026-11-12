"""The keycap legends of QMK's MIDI keycodes, from the firmware's own C.

Firmware 1.13.0 (qmk#427) draws every `QK_MIDI_*` key through `midi_legend()` in
`keyboards/polykybd/midi_legend.c`. The legend is built at runtime from the live
octave, transpose, velocity and channel, so neither static-text switch has an
entry for it and `lang_demo.parse_static_text_map` cannot see it.

The function is pure C (no QMK state, only `quantum_keycodes.h` and
`named_glyphs.h`), so this compiles it with the system C compiler and runs it,
rather than keeping a Python copy that could drift from it. It asks for the
legends at configuration word 0, which is what the keyboard draws before the first
change: QMK's start values with the octave PolyKybd sets, so `MI_C` reads C4. That
is the resting keycap the layout editor shows.

Used by `scripts/export_preview_data.py` and by the checkout path of
`keycap_preview.py`. A tree without `midi_legend.c`, or a machine without a C
compiler, gets None, and those keys fall back to their keycode text.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile

_MAIN = r"""
#include <stdio.h>
#include "midi_legend.h"
#include "quantum_keycodes.h"
int main(void) {
    for (unsigned kc = QK_MIDI; kc <= QK_MIDI_MAX; kc++) {
        const uint32_t* s = midi_legend((uint16_t)kc, 0);
        if (!s) continue;
        printf("%u", kc);
        while (*s) printf(" %u", (unsigned)*s++);
        printf("\n");
    }
    return 0;
}
"""


def _compiler() -> str | None:
    for name in (os.environ.get("CC"), "cc", "gcc", "clang"):
        if name and shutil.which(name):
            return name
    return None


def _midi_names(qmk_root: pathlib.Path) -> dict[int, str]:
    """value -> QMK's long `QK_MIDI_*` name, from the same tree's keycodes.h.

    The long name is the one the layout editor tries for every keycode (the
    header's every alias is a candidate), so it is the one to key the legend on.
    """
    from polyhost.gui.layout_dialog import qmk_keycode_helper as qh
    names = qh.parse_qmk_keycode_header(qmk_root / "quantum" / "keycodes.h",
                                        "qk_keycode_defines")
    return {v: k for k, v in names.items() if k.startswith("QK_MIDI_")}


def midi_legends(pk: str | os.PathLike, log=None) -> dict[str, list[int]] | None:
    """{"QK_MIDI_NOTE_C_0": [codepoint, ...], ...} for the tree at `pk`
    (`<fw>/keyboards/polykybd`), or None when it cannot be built here."""
    pk = pathlib.Path(pk)
    src = pk / "midi_legend.c"
    if not src.exists():
        return None                       # a tree from before the MIDI layer
    cc = _compiler()
    if cc is None:
        if log:
            log("no C compiler: MIDI legends are not previewed")
        return None
    qmk_root = pk.parent.parent
    with tempfile.TemporaryDirectory() as tmp:
        main_c = pathlib.Path(tmp) / "main.c"
        exe = pathlib.Path(tmp) / "midi_legend_dump"
        main_c.write_text(_MAIN, encoding="utf-8")
        inc = [f"-I{p}" for p in (pk, qmk_root / "quantum", qmk_root / "quantum" / "keymap_extras",
                                  qmk_root / "quantum" / "sequencer")]
        # The argv is a list (no shell). Its elements are the compiler found on PATH,
        # fixed flags, and paths this function built from the firmware tree.
        # nosemgrep: dangerous-subprocess-use-audit
        build = subprocess.run([cc, "-std=gnu11", "-O0", "-w", *inc, "-o", str(exe),
                                str(main_c), str(src)],
                               capture_output=True, text=True, timeout=60)
        if build.returncode != 0:
            if log:
                log(f"midi_legend.c did not compile: {build.stderr.strip()[:300]}")
            return None
        # Runs the executable just built in this function's own temporary directory.
        # nosemgrep: dangerous-subprocess-use-audit
        run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    if run.returncode != 0:
        if log:
            log(f"the MIDI legend dump exited {run.returncode}")
        return None
    names = _midi_names(qmk_root)
    out = {}
    for line in run.stdout.splitlines():
        fields = [int(f) for f in line.split()]
        name = names.get(fields[0])
        if name and len(fields) > 1:
            out[name] = fields[1:]
    return out
