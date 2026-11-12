"""QMK keycode names from the shipped `res/keycodes.h` (copied from qmk_firmware).

Qt-free and outside polyhost.gui, so polyctl reads keycode names without importing
the GUI package. The layout editor uses the same functions through
`gui/layout_dialog/qmk_keycode_helper.py`, which re-exports them.
"""

from __future__ import annotations

import pathlib
import re
from pathlib import Path

HEADER_FILE = pathlib.Path(__file__).parent.parent.resolve() / "res" / "keycodes.h"


def parse_qmk_keycode_header(header_path: Path, enum_to_parse: str) -> dict[str, int]:
    """Parse QMK keycode enum from the qmk header file and return dict of keycode names to hex values."""
    text = header_path.read_text(encoding="utf-8", errors="ignore")

    enum_match = re.search(
        rf'enum\s+{enum_to_parse}\s*\{{(.*?)\}};',
        text,
        re.S,
    )
    if not enum_match:
        raise RuntimeError(f"{enum_to_parse} enum not found")

    body = enum_match.group(1)

    entries = {}
    # Two passes, because the enum assigns in two forms. The hex one defines a keycode;
    # the name-to-name one is QMK's short ALIAS (`KC_ENT = KC_ENTER,` -- 128 of them),
    # which a hex-only regex silently skips. A caller that resolves a name typed by a
    # user needs the aliases; one that renders a name back wants the canonical long
    # form, which is why the aliases are added AFTER and callers keep the first name
    # they saw for a value.
    aliases = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue

        m = re.match(r'([A-Z0-9_]+)\s*=\s*(0x[0-9A-Fa-f]+)', line)
        if m:
            entries[m.group(1)] = int(m.group(2), 16)
            continue
        m = re.match(r'([A-Z0-9_]+)\s*=\s*([A-Z][A-Z0-9_]*)\s*,?\s*$', line)
        if m:
            aliases[m.group(1)] = m.group(2)

    # One resolution round handles a chain (an alias of an alias); anything still
    # unresolved names something outside this enum and is dropped rather than guessed.
    for _ in range(len(aliases)):
        progressed = False
        for name, target in list(aliases.items()):
            if name not in entries and target in entries:
                entries[name] = entries[target]
                progressed = True
        if not progressed:
            break

    return entries


def parse_qmk_keycodes(header_path: Path) -> dict[str, int]:
    """Parse QMK keycode enum from the qmk header file and return dict of keycode names to hex values."""
    return parse_qmk_keycode_header(header_path, "qk_keycode_defines")
