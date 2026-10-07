"""Bring the PolyKybd top-view render into the host for the editor's Real mode.

    python scripts/import_real_view.py <topview.png> <topview.json> [width]

The inputs come from the PolyKybd repo (`render/topview.py`, which renders
both halves straight down and writes each key display's image quad). This
scales them to `width` pixels (default 2400; the render is 3200) and writes
`polyhost/res/real_view/board.jpg` + `board.json`, the pair
`gui/layout_dialog/real_board.py` loads. JPEG because the picture is a photo:
~0.4 MB here against ~4 MB as PNG, and Qt reads it everywhere PyQt5 runs.

Every coordinate is scaled with the image, and `mm_per_px` with it, so the
quads stay on the displays at any width.
"""
import json
import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "polyhost" / "res" / "real_view"


def main(png, src_json, width=2400):
    data = json.loads(pathlib.Path(src_json).read_text(encoding="utf-8"))
    im = Image.open(png).convert("RGB")
    if list(im.size) != list(data["size"]):
        raise SystemExit(f"{png} is {im.size}, but {src_json} describes {data['size']}")
    k = width / im.width
    height = round(im.height * k)

    def pt(p):
        return [round(p[0] * k, 2), round(p[1] * k, 2)]

    out = {
        "source": "PolyKybd render/topview.py",
        "image": "board.jpg",
        "size": [width, height],
        "pixel_origin": data["pixel_origin"],
        "corner_order": data["corner_order"],
        "mm_per_px": round(data["mm_per_px"] / k, 5),
        "keys": [{"matrix": e["matrix"], "side": e["side"], "ref": e["ref"],
                  "rotation_deg": e["rotation_deg"], "oled": [pt(p) for p in e["oled"]]}
                 for e in data["keys"]],
        "status_displays": [{"side": s["side"], "size_px": s["size_px"],
                             "bbox": pt(s["bbox"][:2]) + pt(s["bbox"][2:])}
                            for s in data["status_displays"]],
        "expansion_ports": [{"side": e["side"], "quad": [pt(p) for p in e["quad"]],
                             "rotation_deg": e["rotation_deg"]}
                            for e in data.get("expansion_ports", [])],
    }
    # Both files are built before either is written, so input missing a field
    # fails here and leaves the shipped pair as it was, never a new photo
    # beside the old coordinates.
    text = json.dumps(out, indent=1) + "\n"
    photo = im.resize((width, height), Image.LANCZOS)
    OUT.mkdir(parents=True, exist_ok=True)
    photo.save(OUT / "board.jpg", quality=90, optimize=True)
    (OUT / "board.json").write_text(text, encoding="utf-8")
    print(f"wrote {OUT / 'board.jpg'} ({width}x{height}) and board.json, {len(out['keys'])} keys")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2400)
