#!/usr/bin/env python3
"""Fill empty catalog entries from <dir>/<code>.json ({msgid: msgstr}) and check them.

    .venv/bin/python .claude/skills/translate-ui-catalogs/merge_translations.py DIR [CODE ...]

Only EMPTY entries are filled; an existing translation is never overwritten.
Before writing, every pair is checked: same {placeholder} set, same number of
newlines, same <tags> and & mnemonic count. A failing pair is reported and
skipped. Babel's write_po(width=None) round-trips these catalogs byte-identically,
so the diff shows only the filled entries.
"""
import json
import os
import re
import sys

from babel.messages.pofile import read_po, write_po

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
LOCALE = os.path.join(ROOT, "polyhost", "res", "locale")
FIELD = re.compile(r"\{(\w*)\}")
TAG = re.compile(r"<[^>]+>")
MNEMONIC = re.compile(r"(?<!&)&(?![a-zA-Z#0-9]+;|&)(?=\w)")


def problems(src, dst):
    out = []
    if sorted(FIELD.findall(src)) != sorted(FIELD.findall(dst)):
        out.append("placeholders")
    if src.count("\n") != dst.count("\n"):
        out.append("newlines")
    if sorted(TAG.findall(src)) != sorted(TAG.findall(dst)):
        out.append("tags")
    if len(MNEMONIC.findall(src)) != len(MNEMONIC.findall(dst)):
        out.append("& mnemonic")
    return out


def main(argv):
    src_dir = argv[1]
    codes = argv[2:] or sorted(f[:-5] for f in os.listdir(src_dir)
                               if f.endswith(".json") and f != "msgids.json")
    bad = 0
    for code in codes:
        with open(os.path.join(src_dir, code + ".json"), encoding="utf-8") as fh:
            mapping = json.load(fh)
        path = os.path.join(LOCALE, code + ".po")
        with open(path, "rb") as fh:
            cat = read_po(fh)
        filled = 0
        for msg in cat:
            if not isinstance(msg.id, str) or not msg.id or msg.string or msg.id not in mapping:
                continue
            issues = problems(msg.id, mapping[msg.id])
            if issues:
                bad += 1
                print(f"{code}: SKIPPED ({', '.join(issues)}): {msg.id[:60]!r}")
                continue
            msg.string = mapping[msg.id]
            filled += 1
        with open(path, "wb") as fh:
            write_po(fh, cat, width=None, sort_output=False)
        print(f"{code}: filled {filled}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
