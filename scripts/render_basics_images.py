"""Render the keycap pictures of the About dialog's Basics section.

Writes ``polyhost/res/basics/*.png``: each picture is one or more keycaps drawn
by the same renderer as the layout editor (``gui/layout_dialog/keycap_preview``),
from the preview data that ships with the host, so the pictures show what the
keyboard draws. The overlay picture takes its icon from a shipped app overlay
(``res/overlays/gimp_template.mods.png``, the Ctrl variant of S).

Run it again when the keycap renderer, the preview data or the overlay changes:

    QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/render_basics_images.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "polyhost" / "res" / "basics"
SCALE = 2                 # each OLED pixel becomes 2 x 2
BEZEL = 6                 # the dark keycap border around the display, in px
GAP = 14                  # between two keycaps in one picture, in px
ARROW_W = 34              # the space an arrow between two keycaps takes, in px


def _qimage_to_pil(img):
    from PIL import Image
    img = img.convertToFormat(img.Format_RGBA8888)
    ptr = img.constBits()
    ptr.setsize(img.byteCount())
    return Image.frombuffer("RGBA", (img.width(), img.height()), bytes(ptr),
                            "raw", "RGBA", img.bytesPerLine(), 1).copy()


def _ink(panel):
    """The legend colour of a rendered panel: its brightest pixel."""
    import numpy as np
    px = np.array(panel.convert("RGB")).reshape(-1, 3)
    return tuple(int(v) for v in px[px.sum(axis=1).argmax()])


def _keycap(panel):
    """A rendered 72 x 40 panel in a keycap: scaled, with a dark rounded bezel."""
    from PIL import Image, ImageDraw
    face = panel.convert("RGB").resize((panel.width * SCALE, panel.height * SCALE),
                                       Image.NEAREST)
    w, h = face.width + 2 * BEZEL, face.height + 2 * BEZEL
    cap = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(cap)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=10, fill=(38, 40, 46, 255),
                           outline=(90, 94, 104, 255), width=2)
    cap.paste(face, (BEZEL, BEZEL))
    return cap


def _arrow(height):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (ARROW_W, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    mid = height // 2
    grey = (128, 128, 128, 255)
    draw.line((4, mid, ARROW_W - 8, mid), fill=grey, width=3)
    draw.polygon(((ARROW_W - 4, mid), (ARROW_W - 14, mid - 7), (ARROW_W - 14, mid + 7)),
                 fill=grey)
    return img


def _row(caps, arrows=False):
    """Keycaps side by side; with ``arrows``, an arrow between two of them."""
    from PIL import Image
    h = max(c.height for c in caps)
    sep = ARROW_W if arrows else GAP
    w = sum(c.width for c in caps) + sep * (len(caps) - 1)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    x = 0
    for i, cap in enumerate(caps):
        if i and arrows:
            out.alpha_composite(_arrow(h), (x - ARROW_W, 0))
        out.alpha_composite(cap, (x, (h - cap.height) // 2))
        x += cap.width + sep
    return out


def _overlay_cell(path, key, channel):
    import numpy as np
    from PIL import Image
    from polyhost.device.keys import KeyCode
    from polyhost.res.overlay_layout import CH, SLOT_H, SLOT_W, cell_for
    grid = np.array(Image.open(path).convert("RGBA"))
    r, c = cell_for(getattr(KeyCode, key))
    return grid[r * SLOT_H:(r + 1) * SLOT_H, c * SLOT_W:(c + 1) * SLOT_W, CH[channel]]


def _with_overlay(panel, cell):
    """``panel`` with the overlay ``cell`` (0-255 coverage) drawn over it in the
    legend's colour, as the keyboard composes them."""
    import numpy as np
    from PIL import Image
    base = np.array(panel.convert("RGB")).astype(float)
    ink = np.array(_ink(panel), dtype=float)
    alpha = (cell.astype(float) / 255.0)[..., None]
    out = base * (1 - alpha) + ink * alpha
    return Image.fromarray(out.astype("uint8"), "RGB")


def main():
    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    from polyhost.gui.layout_dialog.keycap_preview import KeycapPreview

    preview = KeycapPreview("en-US")
    if not preview.usable:
        raise SystemExit(f"keycap preview unavailable: {preview.reason}")

    def render(keycode, lang="en-US"):
        preview.set_language(lang)
        img = preview.render(keycode, None)
        if img is None:
            raise SystemExit(f"no render for keycode {keycode:#x} in {lang}")
        return _qimage_to_pil(img)

    kc_a, kc_s, kc_1, kc_f1 = 0x04, 0x16, 0x1E, 0x3A
    OUT.mkdir(parents=True, exist_ok=True)
    pictures = {
        # The legend: what a key types, and its Shift character.
        "legend": _row([_keycap(render(kc_a)), _keycap(render(kc_1))]),
        # The same key in four keyboard languages.
        "language": _row([_keycap(render(kc_a, lang))
                          for lang in ("en-US", "ru-RU", "ar-SA", "ja-JP")]),
        # A layer: the 1 key, and the same key while Fn is held.
        "layer": _row([_keycap(render(kc_1)), _keycap(render(kc_f1))], arrows=True),
    }
    s_plain = render(kc_s)
    save = _overlay_cell(ROOT / "polyhost" / "res" / "overlays" / "gimp_template.mods.png",
                         "KC_S", "R")
    # An overlay: S, and S while Ctrl is held in GIMP (Save).
    pictures["overlay"] = _row([_keycap(s_plain), _keycap(_with_overlay(s_plain, save))],
                               arrows=True)
    for name, img in pictures.items():
        path = OUT / f"{name}.png"
        img.save(path, optimize=True)
        print(f"{path.relative_to(ROOT)}  {img.width} x {img.height}")


if __name__ == "__main__":
    main()
