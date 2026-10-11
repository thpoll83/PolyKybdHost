#!/usr/bin/env python3
"""Write the msgids that are empty in ANY catalog to a JSON list.

    .venv/bin/python .claude/skills/translate-ui-catalogs/list_untranslated.py OUT.json

Prints the count per language. After `i18n_strings.py update` every catalog
gains the same new msgids, so the union is normally what each language lacks.
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)
from polyhost import i18n  # noqa: E402

missing = {}
for lang in i18n.LANGUAGES:
    if lang.code == i18n.SOURCE_LANGUAGE:
        continue
    with open(i18n.po_path(lang.code), encoding="utf-8") as fh:
        _header, entries = i18n.parse_po(fh.read())
    empty = [e["msgid"] for e in entries
             if e["msgid"] and not any(e["msgstr"]) and e["msgid_plural"] is None]
    # A plural entry counts only with EVERY form filled: PoTranslations drops a
    # partly translated one, so it shows English for every count.
    plural = [e["msgid"] for e in entries if e["msgid_plural"] and not all(e["msgstr"])]
    print(f"{lang.code}: {len(empty)} empty" + (f", {len(plural)} plural unfinished (do by hand)" if plural else ""))
    for m in empty:
        missing[m] = True
os.makedirs(os.path.dirname(os.path.abspath(sys.argv[1])), exist_ok=True)
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump(list(missing), fh, ensure_ascii=False, indent=1)
print(f"{len(missing)} msgid(s) -> {sys.argv[1]}")
