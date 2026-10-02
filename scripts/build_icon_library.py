#!/usr/bin/env python3
"""Build the overlay icon library, polyhost/res/fontpack/icons.plyi (cmd 42, v20).

    python scripts/build_icon_library.py            # rebuild, bump content_version if bytes change
    python scripts/build_icon_library.py --check    # fail if the shipped files disagree with the id table

REBUILD IN BATCHES, not per overlay change. Every rebuild bumps content_version,
and every keyboard re-flashes the 256 KiB slot on its next connect. A new icon
missing from the library costs nothing in correctness: the send path uses the
library only on an exact pixel match and otherwise uploads the bitmap. So
``--check`` (a test) does NOT fail on new eligible icons. It lists them as
pending and fails only when the shipped files no longer match the frozen id
table. Rebuild when the pending list is worth a re-flash, for example before a
release.

SELECTION (OVERLAY_ICON_LIBRARY_DESIGN.md §2.1). An icon is in the library when
its rendered 72x40 cell is:
- a Fluent or Material Symbols icon, or drawn by the shared concept renderer
  (``concept:``), in any spec under res/overlay_sources; or
- a custom drawing whose PIXELS appear in two or more apps (sublime and
  sublime_mac count as one).
App-only drawings, text labels and the ESC program marks stay bitmap uploads.

Only cells whose exact bytes also occur in a SHIPPED template are kept: the send
path fills an image only on an exact pixel match (services/icon_library.py), so a
cell the templates never carry would be dead weight in flash.

IDS are frozen and append-only (res/fontpack/icon_ids.yaml, like the ISO index
table): an existing icon keeps its id, a new one takes the next free id, and a
retired one keeps its id and glyph. The id is the glyph index in the bundle.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import yaml  # noqa: E402

from polyhost.services import icon_library  # noqa: E402

RES = ROOT / "polyhost" / "res"
SOURCES = RES / "overlay_sources"
FONTPACK = RES / "fontpack"
IDS_FILE = FONTPACK / "icon_ids.yaml"
PLYI_FILE = FONTPACK / "icons.plyi"
MANIFEST = FONTPACK / "bundles.json"
SLOT_OFFSET, SLOT_SIZE = 0x1C0000, 0x40000      # fontpack_layout.h, layout v2
LIB_KINDS = {"fluent", "material", "lexicon"}


def _family(name: str) -> str:
    return "sublime" if name.startswith("sublime") else name


def _specs():
    for y in sorted(list(SOURCES.glob("*/bindings.yaml")) + list(SOURCES.glob("*/*.yaml"))):
        spec = yaml.safe_load(y.read_text(encoding="utf-8"))
        if isinstance(spec, dict) and "bindings" in spec:
            name = str(y.relative_to(SOURCES)).replace("/bindings.yaml", "").replace(".yaml", "")
            yield name, y, spec


def _platform_results(g, spec: dict, base: Path):
    """Every artwork set the generator writes for this spec, not only Windows.

    A binding scoped `only: [macos]` (or to Linux, or one desktop) appears in
    that platform's set alone, so rendering only the default set left its icon
    out of the library selection entirely."""
    yield g.generate(spec, base)
    if g.spec_needs_macos_set(spec):
        yield g.generate(spec, base, platform=g.PLAT_MACOS)
    if g.spec_needs_linux_set(spec):
        yield g.generate(spec, base, platform=g.PLAT_LINUX)
    for member in g.LINUX_MEMBERS:
        if g.spec_needs_member_set(spec, member):
            yield g.generate(spec, base, platform=member)


def _spec_cells(y: Path, spec: dict):
    """[(kind, name, packed 360-byte frame)] for every cell the generator draws,
    on every platform it writes a set for."""
    import generate_app_overlays as g
    base = y.parent
    fmap = {}
    fp = base / "fetch_icons.py"
    if fp.exists():
        for k, v in re.findall(r'"([\w\-.]+)"\s*:\s*"([^"]+)"', fp.read_text(encoding="utf-8")):
            fmap[k.replace(".png", "")] = v
    kind_of = {}
    for b in spec["bindings"]:
        ic = b.get("icon") or ""
        stem = os.path.splitext(os.path.basename(ic))[0]
        src = str(b.get("source", ""))
        if stem in fmap or src.startswith("ms-fluent"):
            kind_of[ic] = "fluent"
        elif src.startswith("material"):
            kind_of[ic] = "material"
        else:
            kind_of[ic] = "custom"
    out = []
    for res in _platform_results(g, spec, base):
        for p in res["placed"]:
            if p["mod"] not in g.Modifier.__members__:
                continue                                  # the ESC program mark
            mod = g.Modifier[p["mod"]]
            arr = next(res[t] for t, chmap in (("primary", g.PRIMARY_CH), ("combo", g.COMBO_CH),
                                                ("extra", g.EXTRA_CH), ("gui", g.GUI_CH))
                       if mod in chmap)
            src = str(p["src"])
            if src.startswith("concept:"):
                kind = "lexicon"
            elif src.startswith("label:"):
                kind = "label"
            else:
                kind = kind_of.get(p["src"], "custom")
            r, c = p["cell"]
            m = arr[r * g.SLOT_H:(r + 1) * g.SLOT_H, c * g.SLOT_W:(c + 1) * g.SLOT_W,
                    g.CH[p["ch"]]] > 0
            if m.any():
                out.append((kind, src, np.packbits(m).tobytes()))
    return out


def _shipped_frames() -> set[bytes]:
    """Packed bytes of every image the shipped templates upload."""
    from polyhost.device.device_settings import DeviceSettings
    from polyhost.device.im_converter import ImageConverter
    from polyhost.device.keys import Modifier
    import logging
    logging.getLogger("PolyHost").setLevel(logging.ERROR)
    mapping = yaml.safe_load((RES / "overlay-mapping.poly.yaml").read_text(encoding="utf-8"))
    files = set()

    def walk(node):
        if isinstance(node, dict):
            ov = node.get("overlay")
            if ov:
                files.update([ov] if isinstance(ov, str) else ov)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(mapping)
    seen = set()
    for f in sorted(files):
        conv = ImageConverter(DeviceSettings())
        if conv.open(str(RES / "overlays" / f)) is False:
            continue
        for mod in Modifier:
            for ov in (conv.extract_overlays(mod) or {}).values():
                seen.add(bytes(ov.all_bytes))
    return seen


def select() -> dict[bytes, str]:
    """{packed frame: name} of every icon the rule puts in the library."""
    kinds = collections.defaultdict(set)
    apps = collections.defaultdict(set)
    names = {}
    for name, y, spec in _specs():
        for kind, src, frame in _spec_cells(y, spec):
            kinds[frame].add(kind)
            apps[frame].add(_family(name))
            names.setdefault(frame, src)
    shipped = _shipped_frames()
    out = {}
    for frame, ks in kinds.items():
        if frame not in shipped:
            continue
        if ks & LIB_KINDS or ("custom" in ks and len(apps[frame]) >= 2):
            out[frame] = names[frame]
    return out


def _key(frame: bytes) -> str:
    return hashlib.sha256(frame).hexdigest()[:20]


def assign_ids(selected: dict[bytes, str], ids_doc: list,
               previous: list[bytes]) -> tuple[list, list[bytes]]:
    """Append new icons to the frozen id table. Returns (table, frames by id).

    ``previous`` is the frame list of the shipped icons.plyi: a retired icon's
    pixels come from there, so the table itself stays small."""
    by_key = {e["key"]: e for e in ids_doc}
    frames_by_key = {_key(f): f for f in selected}
    table = [dict(e) for e in ids_doc]
    for frame, name in sorted(selected.items(), key=lambda kv: (kv[1], _key(kv[0]))):
        if _key(frame) not in by_key:
            table.append({"id": len(table), "key": _key(frame), "name": name})
    frames = []
    for e in table:
        f = frames_by_key.get(e["key"])
        if f is None:
            # Retired: the template no longer carries it, but the id and glyph
            # stay, so the bundle must still carry the pixels.
            if e["id"] >= len(previous):
                sys.exit(f"icon id {e['id']} is retired but not in the shipped icons.plyi")
            f = previous[e["id"]]
        frames.append(f)
    return table, frames


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="fail if the shipped files disagree with the frozen id table; "
                         "new eligible icons are only reported as pending")
    args = ap.parse_args(argv)

    ids_doc = []
    if IDS_FILE.exists():
        ids_doc = yaml.safe_load(IDS_FILE.read_text(encoding="utf-8")) or []
    selected = select()
    known = {e["key"] for e in ids_doc}
    pending = sorted(n for f, n in selected.items() if _key(f) not in known)
    if args.check:
        # Rebuild from the frozen table alone: the shipped files must match it,
        # but a new icon waits for the next deliberate rebuild.
        selected = {f: n for f, n in selected.items() if _key(f) in known}
    previous = icon_library.parse(PLYI_FILE.read_bytes())[1] if PLYI_FILE.exists() else []
    table, frames = assign_ids(selected, ids_doc, previous)

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entry = next((b for b in manifest["bundles"] if b["id"] == "icons"), None)
    version = entry["content_version"] if entry else 0
    data = icon_library.build(frames, version)
    old = PLYI_FILE.read_bytes() if PLYI_FILE.exists() else b""
    if data != old:
        version += 1
        data = icon_library.build(frames, version)
    if len(data) > SLOT_SIZE:
        sys.exit(f"icons.plyi is {len(data)} B, over its {SLOT_SIZE} B slot")

    ids_text = ("# Frozen overlay icon ids (HID cmd 42). APPEND-ONLY: an id never changes\n"
                "# and a retired icon keeps its entry. Written by scripts/build_icon_library.py.\n"
                + yaml.safe_dump(table, sort_keys=False, width=200))
    new_entry = {"id": "icons", "index": icon_library.BUNDLE_ID, "file": "icons.plyi",
                 "kind": "icons", "content_version": version, "size": len(data),
                 "slot_offset": SLOT_OFFSET, "slot_size": SLOT_SIZE,
                 "sha256": hashlib.sha256(data).hexdigest()[:16]}
    bundles = [b for b in manifest["bundles"] if b["id"] != "icons"] + [new_entry]
    manifest = {**manifest, "layout_version": 2, "bundle_count": len(bundles), "bundles": bundles}
    manifest_text = json.dumps(manifest, indent=2) + "\n"

    if args.check:
        stale = [p.name for p, want in ((PLYI_FILE, data), (IDS_FILE, ids_text.encode()),
                                        (MANIFEST, manifest_text.encode()))
                 if not p.exists() or p.read_bytes() != want]
        if data != old:
            stale.append("icons.plyi (content)")
        if stale:
            print("stale:", ", ".join(sorted(set(stale))))
            return 1
        print(f"OK: {len(frames)} icons, {len(data)} B, content v{version}")
        if pending:
            print(f"pending: {len(pending)} new icon(s) ride as bitmap uploads until the "
                  f"next rebuild: {', '.join(pending)}")
        return 0
    PLYI_FILE.write_bytes(data)
    IDS_FILE.write_text(ids_text, encoding="utf-8")
    MANIFEST.write_text(manifest_text, encoding="utf-8")
    kinds = collections.Counter(n.split(":")[0] if ":" in n else "custom" for n in selected.values())
    print(f"icons.plyi: {len(frames)} icons ({dict(kinds)}), {len(data):,} B of {SLOT_SIZE:,}, "
          f"content v{version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
