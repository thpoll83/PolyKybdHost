"""The rendered top view of the board, behind the editor's keys in Real mode.

`polyhost/res/real_view/board.jpg` is an orthographic Blender render straight
down on both halves (PolyKybd `render/topview.py`, brought in with
`scripts/import_real_view.py`), and `board.json` gives, per key display, the
72x40 active area as four image pixels in the OLED's own order (top-left,
top-right, bottom-right, bottom-left), keyed by the KLE `"row,col"` label, plus
each status display's box.

In Real mode the editor shows that picture instead of the drawn case plate, and
moves every key so that its display rect (`RenderableKey.display_rect`) lands
exactly on its photographed OLED: the key then paints only the simulated panel,
and the photo supplies the cap, switch, plate and case around it. The keys sit
where the PCB puts them, not where the KLE does; the two disagree by up to
~4.5 mm, which on a photo would show as every legend sliding off its screen.

The two keys with no display (they sit under the rotary encoder) are placed by
a per-half affine fit from their KLE position to the photo, from the 36 keys
that do have one.

Fails soft like the plate: no files, or a file that does not parse, and `load`
returns None, so Real mode keeps its drawn board.
"""
import json
import pathlib
from dataclasses import dataclass

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QPixmap, QPolygonF, QTransform
from PyQt5.QtWidgets import QGraphicsPixmapItem

from polyhost.gui.layout_dialog.board_plate import SCREEN_BOX, SCREEN_SIDE, Z_PLATE, Z_SCREEN

RES = pathlib.Path(__file__).parent.parent.parent.resolve() / "res" / "real_view"
U_MM = 19.05


@dataclass(frozen=True)
class RealBoard:
    image: pathlib.Path
    size: tuple                 # (w, h) photo pixels
    mm_per_px: float
    quads: dict                 # (row, col) -> four (x, y) photo pixels, OLED order
    status: dict                # side -> (x0, y0, x1, y1) photo pixels

    def scale(self, key_scale):
        """Scene units per photo pixel, so one key unit is `key_scale` as in the KLE view."""
        return key_scale * self.mm_per_px / U_MM

    def scene_quad(self, key, key_scale):
        s = self.scale(key_scale)
        return [QPointF(x * s, y * s) for x, y in self.quads[key]]


def load(path=RES / "board.json"):
    """The photo and its key quads, or None when it is not shipped or unreadable."""
    try:
        path = pathlib.Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        image = path.parent / data["image"]
        if not image.is_file():
            return None
        quads = {}
        for k in data["keys"]:
            row, col = (int(v) for v in k["matrix"].split(","))
            quad = tuple((float(x), float(y)) for x, y in k["oled"])
            if len(quad) != 4:
                return None
            quads[(row, col)] = quad
        status = {s["side"]: tuple(float(v) for v in s["bbox"]) for s in data.get("status_displays", [])}
        return RealBoard(image=image, size=tuple(data["size"]), mm_per_px=float(data["mm_per_px"]),
                         quads=quads, status=status)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def add_photo(scene, board, key_scale):
    """Put the photo and the two status-screen slots in `scene`; returns the items.

    The screen slots carry the same SCREEN_SIDE / SCREEN_BOX tags as the drawn
    board's, so `board_plate.set_screen_images` paints them unchanged.
    """
    pix = QPixmap(str(board.image))
    if pix.isNull():
        return []
    s = board.scale(key_scale)
    photo = QGraphicsPixmapItem(pix)
    photo.setTransformationMode(Qt.SmoothTransformation)
    photo.setScale(s * board.size[0] / pix.width())
    photo.setZValue(Z_PLATE)
    photo.setAcceptedMouseButtons(Qt.NoButton)
    scene.addItem(photo)
    items = [photo]
    for side, (x0, y0, x1, y1) in board.status.items():
        shot = QGraphicsPixmapItem()
        shot.setTransformationMode(Qt.SmoothTransformation)
        shot.setData(SCREEN_SIDE, side)
        shot.setData(SCREEN_BOX, (x0 * s, y0 * s, (x1 - x0) * s, (y1 - y0) * s))
        shot.setPos(x0 * s, y0 * s)
        shot.setZValue(Z_SCREEN)
        shot.setAcceptedMouseButtons(Qt.NoButton)
        scene.addItem(shot)
        items.append(shot)
    return items


def scene_rect(board, key_scale):
    s = board.scale(key_scale)
    return QRectF(0, 0, board.size[0] * s, board.size[1] * s)


def quad_transform(rect, quad):
    """The item transform that maps `rect` (item coordinates) onto `quad` (scene)."""
    src = QPolygonF([QPointF(rect.left(), rect.top()), QPointF(rect.right() + 1, rect.top()),
                     QPointF(rect.right() + 1, rect.bottom() + 1), QPointF(rect.left(), rect.bottom() + 1)])
    t = QTransform()
    if not QTransform.quadToQuad(src, QPolygonF(quad), t):
        return None
    return t


def fit_affine(pairs):
    """Least-squares affine QTransform taking each pair's first point to its second."""
    import numpy as np
    if len(pairs) < 3:
        return QTransform()
    a = np.array([[p.x(), p.y(), 1.0] for p, _ in pairs])
    b = np.array([[q.x(), q.y()] for _, q in pairs])
    m, *_ = np.linalg.lstsq(a, b, rcond=None)     # 3x2: [x y 1] @ m = [x' y']
    return QTransform(m[0, 0], m[0, 1], m[1, 0], m[1, 1], m[2, 0], m[2, 1])
