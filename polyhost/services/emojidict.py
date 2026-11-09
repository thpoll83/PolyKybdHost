"""Emoji search dictionaries (font-pack bundle ``emojidict``, slot 9).

The keyboard's emoji layer searches by keyword through a dictionary flashed to
font-pack slot 9 (firmware: keyboards/polykybd/emoji/EMOJI_SEARCH.md). This host
ships every dictionary in ``polyhost/res/emojidict/`` as ``<id>.plyd.gz`` with the
builder's ``manifest.json`` (qmk ``emoji_dict.py build-all``, imported by
``scripts/import_emojidict.py``), and flashes the one the ``emoji_search_dict``
setting names.

Which dictionary a keyboard holds is read from GET_ID's version block: a
dictionary bundle's content_version is ``(number << 8) | revision``, with
``number`` its fixed place in the builder's dictionaries.tsv. So no command of its
own is needed, and a keyboard with fewer than 10 slots (firmware before font-pack
layout v4) simply has no slot 9.
"""
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

import platformdirs

BUNDLE_ID = 9           # FONTPACK_EMOJIDICT_BUNDLE_ID (fontpack_layout.h)
DEFAULT_DICT = "en"


def _res_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "res" / "emojidict"


def load_manifest(res: Path | None = None) -> dict | None:
    """The shipped manifest, or None if none is shipped. Entries whose file is
    missing are dropped."""
    d = res or _res_dir()
    mf = d / "manifest.json"
    if not mf.is_file():
        return None
    try:
        doc = json.loads(mf.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entries = [e for e in doc.get("dictionaries", []) if (d / e.get("file", "")).is_file()]
    if not entries:
        return None
    doc["dictionaries"] = entries
    doc["_dir"] = str(d)
    return doc


def find(manifest: dict | None, dict_id: str) -> dict | None:
    for e in (manifest or {}).get("dictionaries", []):
        if e["id"] == dict_id:
            return e
    return None


def identify(manifest: dict | None, device_version: int) -> tuple[dict | None, int]:
    """The shipped dictionary a device's slot-9 version names, and its revision
    there. (None, 0) for an empty slot or a number this host does not know."""
    if not device_version:
        return None, 0
    number, revision = device_version >> 8, device_version & 0xFF
    for e in (manifest or {}).get("dictionaries", []):
        if e["number"] == number:
            return e, revision
    return None, revision


def label(entry: dict) -> str:
    """Menu text: the native name, then the English one when it differs."""
    nat, en = entry.get("native", ""), entry.get("name", "")
    return nat if not en or en == nat else f"{nat} — {en}"


def _cache_dir() -> Path:
    return Path(platformdirs.user_cache_dir("PolyKybdHost")) / "emojidict"


def unpacked_path(manifest: dict, entry: dict, cache: Path | None = None) -> str:
    """A plain .plyd of ``entry`` for the flasher, unpacked into the cache once
    (keyed by its sha256 prefix, so an updated dictionary is unpacked again)."""
    cache = cache or _cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"{entry['id']}-{entry['sha256']}.plyd"
    if not out.is_file():
        data = gzip.decompress((Path(manifest["_dir"]) / entry["file"]).read_bytes())
        tmp = out.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, out)
    return str(out)


def bundle_entry(manifest: dict | None, dict_id: str, cache: Path | None = None) -> dict | None:
    """The selected dictionary as a font-pack bundle entry, in the shape of
    ``fontpack_bundle.load_bundle_manifest()`` entries, so the connect-time flash
    pass, the status, the forced re-flash and the wipe handle slot 9 like any other
    bundle. ``kind`` "emojidict" makes it stale on any version MISMATCH (a different
    dictionary can have a lower number) and never assumes the slot exists."""
    entry = find(manifest, dict_id) or find(manifest, DEFAULT_DICT)
    if entry is None:
        return None
    return {"id": "emojidict", "index": BUNDLE_ID, "kind": "emojidict",
            "dict_id": entry["id"], "content_version": entry["content_version"],
            "size": entry["size"], "path": unpacked_path(manifest, entry, cache)}
