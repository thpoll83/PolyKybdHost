#!/usr/bin/env python3
"""Import the emoji search dictionaries built by the firmware repo.

    cd ../qmk_firmware/keyboards/polykybd/emoji
    python3 emoji_dict.py build-all /tmp/emojidict
    cd -; python3 scripts/import_emojidict.py /tmp/emojidict

Writes polyhost/res/emojidict/<id>.plyd.gz (gzip, so the 79 dictionaries ship in
about 3.7 MB instead of 5.3 MB) and manifest.json, whose "file" fields name the
.gz files. The sha256 in the manifest stays the one of the plain .plyd, which is
what the keyboard holds.
"""
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "polyhost" / "res" / "emojidict"


def main(src: str) -> int:
    src_dir = Path(src)
    manifest = json.loads((src_dir / "manifest.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.plyd.gz"):
        old.unlink()
    total = 0
    for e in manifest["dictionaries"]:
        data = (src_dir / e["file"]).read_bytes()
        if hashlib.sha256(data).hexdigest()[:16] != e["sha256"] or len(data) != e["size"]:
            raise SystemExit(f"{e['file']}: size or sha256 does not match the manifest")
        name = e["file"] + ".gz"
        # mtime=0 keeps the .gz byte-identical across imports of the same data.
        packed = gzip.compress(data, compresslevel=9, mtime=0)
        (OUT / name).write_bytes(packed)
        total += len(packed)
        e["file"] = name
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8")
    print(f"{len(manifest['dictionaries'])} dictionaries, {total:,} B in {OUT}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))
