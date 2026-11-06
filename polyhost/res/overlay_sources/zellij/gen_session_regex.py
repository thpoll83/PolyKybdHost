#!/usr/bin/env python3
"""Print the `titles-match` key that finds Zellij 0.43.1+ by its window title.

Since 0.43.1 Zellij writes "<session> | <pane title>" (or "<session>" alone)
into the terminal title, and that title does not name Zellij. A session that
was started without a name gets a generated "<adjective>-<noun>" name from two
fixed lists in `zellij-utils/src/sessions.rs` (`ADJECTIVES`, `NOUNS`), so the
mapping matches those names. This script reads the two lists at each tag in
TAGS, takes their union (v0.45.1 corrected `iguanadon` to `iguanodon`), and
prints the regex for `overlay-mapping.poly.yaml`. See SOURCES.md.

    python polyhost/res/overlay_sources/zellij/gen_session_regex.py
    python polyhost/res/overlay_sources/zellij/gen_session_regex.py --check
"""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

TAGS = ("v0.43.1", "v0.45.1")
URL = "https://raw.githubusercontent.com/zellij-org/zellij/{}/zellij-utils/src/sessions.rs"
MAPPING = Path(__file__).resolve().parents[2] / "overlay-mapping.poly.yaml"


def _words(src: str, name: str) -> list[str]:
    m = re.search(name + r": &\[&'static str\] = &\[(.*?)\];", src, re.S)
    if m is None:
        raise SystemExit(f"{name} not found")
    words = re.findall(r'"([a-z]+)"', m.group(1))
    if not words:
        raise SystemExit(f"{name} is empty")
    return words


def regex() -> str:
    adjectives: set[str] = set()
    nouns: set[str] = set()
    for tag in TAGS:
        req = urllib.request.Request(URL.format(tag), headers={"User-Agent": "PolyKybdHost"})
        with urllib.request.urlopen(req, timeout=60) as r:
            src = r.read().decode("utf-8")
        adjectives.update(_words(src, "ADJECTIVES"))
        nouns.update(_words(src, "NOUNS"))
    return ("^(?:" + "|".join(sorted(adjectives)) + ")-(?:" + "|".join(sorted(nouns))
            + r")(?:$| \| )")


def main() -> int:
    rx = regex()
    if "--check" in sys.argv[1:]:
        if f"? '{rx}'" not in MAPPING.read_text(encoding="utf-8"):
            print("overlay-mapping.poly.yaml does not contain the current regex")
            return 1
        print("ok")
        return 0
    print(rx)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
