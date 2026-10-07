"""Real mode on the rendered top view: every key lands on its photographed OLED.

The point of the photo is that a legend sits ON its screen. So the dialog test
does not check that a transform was set; it maps each key's display rect into
the scene and compares it with the quad the render measured.
"""
import json
import math
import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import QPointF, QRectF, Qt
    from PyQt5.QtGui import QColor, QTransform
    from PyQt5.QtWidgets import QApplication
except ImportError as e:                      # pragma: no cover - PyQt5 not installed
    _IMPORT_ERR = e
else:
    _IMPORT_ERR = None
    from polyhost.gui.layout_dialog import board_plate as bp
    from polyhost.gui.layout_dialog import kb_layout_dialog as kb
    from polyhost.gui.layout_dialog import real_board as rb
    from polyhost.gui.layout_dialog.renderable_key import key_transform
    _APP = QApplication.instance() or QApplication([])

LAYERS = ["Qwerty", "Fn", "Numpad", "Utility"]


def setUpModule():
    """Pin the QApplication for the life of the module (see kb_layout_screens_test)."""
    if _IMPORT_ERR is None:
        assert _APP is not None


class _Core:
    def keymap_layer_names(self):
        return True, list(LAYERS)

    def keymap_layer_count(self):
        return True, len(LAYERS)

    def keymap_buffer(self, *a, **k):
        return True, [0] * (8 * 10 * len(LAYERS))

    def keymap_default_layer(self):
        return True, 0

    def macro_list(self):
        return True, {"macros": [], "count": 0}

    def macro_set(self, *a, **k):
        return True, ""

    def macro_clear(self, *a, **k):
        return True, ""

    def keymap_set(self, *a, **k):
        return True, ""

    def subscribe(self, cb):
        return lambda: None


class _Settings:
    MATRIX_COLUMNS = 8
    MATRIX_ROWS = 10


@unittest.skipIf(_IMPORT_ERR is not None, "PyQt5 not installed")
class RealBoardLoadTest(unittest.TestCase):
    def test_the_shipped_view_has_every_display(self):
        board = rb.load()
        self.assertIsNotNone(board, "the shipped real view is missing or broken")
        self.assertEqual(len(board.quads), 72)        # 74 keys, 72 OLEDs
        self.assertNotIn((3, 7), board.quads)         # under the encoder, no display
        self.assertNotIn((8, 0), board.quads)
        self.assertEqual(set(board.status), {"left", "right"})
        self.assertEqual(set(board.ports), {"left", "right"})
        w, h = board.size
        for quad in board.quads.values():
            for x, y in quad:
                self.assertTrue(0 <= x <= w and 0 <= y <= h)

    def test_missing_or_broken_files_fail_soft(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(rb.load(os.path.join(d, "board.json")))
            path = os.path.join(d, "board.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"image": "board.jpg", "size": [10, 10], "mm_per_px": 1, "keys": []}, f)
            self.assertIsNone(rb.load(path), "a json without its image must not load")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{not json")
            self.assertIsNone(rb.load(path))
            # valid json, image present, but metadata the scene code would index past
            with open(os.path.join(d, "board.jpg"), "wb") as f:
                f.write(b"\xff\xd8")
            for bad in ({"size": [10]}, {"size": [10, 0]}, {"mm_per_px": 0},
                        {"keys": [{"matrix": 12, "oled": [[0, 0]] * 4}]},
                        {"status_displays": [{"side": "left", "bbox": [1, 2]}]}):
                meta = {"image": "board.jpg", "size": [10, 10], "mm_per_px": 1, "keys": [], **bad}
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(meta, f)
                self.assertIsNone(rb.load(path), bad)

    def test_fit_affine_recovers_a_transform(self):
        truth = QTransform().translate(30, -12).rotate(7).scale(1.3, 1.3)
        pts = [QPointF(x, y) for x, y in ((0, 0), (100, 0), (0, 50), (80, 90), (40, 10))]
        fit = rb.fit_affine([(p, truth.map(p)) for p in pts])
        for p in (QPointF(13, 77), QPointF(-20, 5)):
            a, b = fit.map(p), truth.map(p)
            self.assertAlmostEqual(a.x(), b.x(), places=6)
            self.assertAlmostEqual(a.y(), b.y(), places=6)


@unittest.skipIf(_IMPORT_ERR is not None, "PyQt5 not installed")
class RealModeDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from polyhost.gui import oled_look
        if not oled_look.available():
            raise unittest.SkipTest("Pillow unavailable: no Real mode")
        cls.board = rb.load()
        # a failure, not a skip: the shipped view IS what these tests cover
        assert cls.board is not None, "the shipped real view is missing or broken"
        cls.dlg = kb.KbLayoutDialog(_Core(), _Settings())

    def tearDown(self):
        self.dlg.set_keycap_mode(kb.KEYCAP_SYMBOL)

    def test_REAL_puts_every_display_on_its_photographed_OLED(self):
        self.dlg.set_keycap_mode(kb.KEYCAP_REAL)
        cols = _Settings.MATRIX_COLUMNS
        placed = 0
        for (row, col), quad in self.board.quads.items():
            item = self.dlg.keys[row * cols + col]
            r = QRectF(item.display_rect())
            corners = (r.topLeft(), QPointF(r.right(), r.top()), r.bottomRight(),
                       QPointF(r.left(), r.bottom()))
            for got, want in zip(corners, self.board.scene_quad((row, col), kb.KEY_SCALE)):
                got = item.mapToScene(got)
                self.assertAlmostEqual(got.x(), want.x(), delta=1.5, msg=f"{row},{col}")
                self.assertAlmostEqual(got.y(), want.y(), delta=1.5, msg=f"{row},{col}")
            placed += 1
        self.assertEqual(placed, 72)

    def test_REAL_shows_the_photo_and_its_status_screens(self):
        self.dlg.set_keycap_mode(kb.KEYCAP_REAL)
        sides = {i.data(bp.SCREEN_SIDE) for i in self.dlg._board_items} - {None}
        self.assertEqual(sides, {"left", "right"})
        self.assertEqual(self.dlg.view.sceneRect(), rb.scene_rect(self.board, kb.KEY_SCALE))

    def test_leaving_REAL_puts_the_keys_back_on_the_KLE_grid(self):
        self.dlg.set_keycap_mode(kb.KEYCAP_REAL)
        self.dlg.set_keycap_mode(kb.KEYCAP_PREVIEW)
        km = self.dlg.key_matrix
        minx = min(p["x"] for p in km.values())
        miny = min(p["y"] for p in km.values())
        for info in km.values():
            item = self.dlg.keys[info["row"] * _Settings.MATRIX_COLUMNS + info["col"]]
            self.assertEqual(item.transform(), key_transform(info, minx, miny, kb.KEY_SCALE))
            self.assertFalse(item._photo)

    def test_on_the_photo_a_key_answers_only_over_its_display(self):
        self.dlg.set_keycap_mode(kb.KEYCAP_REAL)
        for (row, col) in self.board.quads:
            item = self.dlg.keys[row * _Settings.MATRIX_COLUMNS + col]
            r = QRectF(item.display_rect())
            self.assertTrue(item.contains(r.center()), f"{row},{col}")
            # the tile's lower part, below the panel: another key's cap on the photo
            below = QPointF(r.center().x(), (r.bottom() + item.boundingRect().bottom()) / 2)
            self.assertFalse(item.contains(below), f"{row},{col}")
        self.dlg.set_keycap_mode(kb.KEYCAP_PREVIEW)
        item = self.dlg.keys[2]
        self.assertTrue(item.contains(item.boundingRect().center()))

    def test_on_the_photo_no_badge_floats_over_the_picture(self):
        self.dlg.set_keycap_mode(kb.KEYCAP_REAL)
        for (row, col) in self.board.quads:
            item = self.dlg.keys[row * _Settings.MATRIX_COLUMNS + col]
            item.set_display("A", "MO", "#FFCC44")
            self.assertFalse(item.badge.isVisible(), f"{row},{col}")
            item.set_photo_mode(False)
            self.assertTrue(item.badge.isVisible(), f"{row},{col}")
            item.set_photo_mode(True)
            self.assertFalse(item.badge.isVisible(), f"{row},{col}")

    def test_REAL_has_a_white_scene_and_leaving_it_resets(self):
        self.dlg.set_keycap_mode(kb.KEYCAP_REAL)
        self.assertEqual(self.dlg.scene.backgroundBrush().color(), QColor(Qt.white))
        self.assertEqual(self.dlg.scene.backgroundBrush().style(), Qt.SolidPattern)
        self.dlg.set_keycap_mode(kb.KEYCAP_PREVIEW)
        self.assertNotEqual(self.dlg.scene.backgroundBrush().color(), QColor(Qt.white))

    def test_keys_without_a_display_are_a_label_alone(self):
        self.dlg.set_keycap_mode(kb.KEYCAP_REAL)
        cols = _Settings.MATRIX_COLUMNS
        loose = [i for i in self.dlg.keys.values()
                 if (i.matrix_index // cols, i.matrix_index % cols) not in self.board.quads]
        self.assertEqual(len(loose), 2)
        for item in loose:
            item.set_display("Enc", "MO", "#FFCC44")
            self.assertTrue(item._label_only)
            self.assertTrue(item.text.isVisible())
            self.assertFalse(item.badge.isVisible())
            # only the label answers: not the empty tile around it
            self.assertFalse(item.contains(item.boundingRect().bottomLeft() + QPointF(2, -2)))
            self.assertTrue(item.contains(item.text.mapRectToParent(item.text.boundingRect()).center()))
        self.dlg.set_keycap_mode(kb.KEYCAP_PREVIEW)
        self.assertFalse(any(i._label_only for i in self.dlg.keys.values()))

    def test_expansion_labels_sit_on_their_lids_at_the_lids_angle(self):
        self.dlg.set_keycap_mode(kb.KEYCAP_REAL)
        cols = _Settings.MATRIX_COLUMNS
        for side, (row, col) in (("left", (3, 7)), ("right", (8, 0))):
            item = self.dlg.keys[row * cols + col]
            centre, angle = self.board.port_pose(side, kb.KEY_SCALE)
            got = item.mapToScene(item.label_anchor())
            self.assertAlmostEqual(got.x(), centre.x(), delta=0.5, msg=side)
            self.assertAlmostEqual(got.y(), centre.y(), delta=0.5, msg=side)
            t = item.transform()
            self.assertAlmostEqual(math.degrees(math.atan2(t.m12(), t.m11())), angle, delta=0.1)
            # the label really is centred there, whatever its text
            item.set_display("Enc", "", None)
            r = item.text.mapRectToParent(item.text.boundingRect())
            self.assertAlmostEqual(r.center().y(), item.label_anchor().y(), delta=0.5)

    def test_the_selected_key_survives_the_rebuild(self):
        self.dlg.mouseClickEvent(self.dlg.keys[2])
        self.dlg.keys[2].setSelected(True)
        self.dlg.set_keycap_mode(kb.KEYCAP_REAL)
        self.assertIs(self.dlg.selected_key, self.dlg.keys[2])
        self.assertTrue(self.dlg.keys[2].isSelected())


if __name__ == "__main__":
    unittest.main()
