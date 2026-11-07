#!/usr/bin/env python3
"""Fetch the Amiberry shortcut icons.

Action icons are Material Symbols (Apache-2.0) through `icon_fetch`. The ESC
mark is a drawn "AB" tile (`program_marks`). See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/amiberry/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, program_marks  # noqa: E402

FLUENT = {
    "gui":    "ms:menu",
    "freeze": "ms:ac_unit",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    program_marks.ensure(out / "amiberry.png", "AB")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
