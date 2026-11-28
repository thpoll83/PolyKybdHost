"""Overlay images per physical key (firmware protocol v40, device/key_images.py):
the `.keys.png` written by services/user_overlays, its converter, and the send path
against the emulated keyboard on both sides of the gate."""
import shutil
import tempfile
import threading
import unittest
import unittest.mock as mock

from polyhost.device import key_images
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import Modifier
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.poly_kybd import KEY_OVERLAY_MIN_PROTOCOL
from polyhost.device.poly_kybd_mock import PolyKybdMock
from polyhost.services import user_overlays as uo

BOX = [{"rect": [0, 0, 72, 40]}]


class KeyImageFileTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="polykybd-keys-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def _star(self, bindings):
        uo.save_set("*", bindings, self.root)
        return [f for f in uo.star_files(self.root) if key_images.is_key_image_file(f)]

    def test_the_file_holds_each_key_by_matrix_index(self):
        files = self._star([
            {"key": "L:1.1", "follow": "key", "drawing": BOX},                    # (0, 0)
            {"key": "R:1.1", "follow": "key", "drawing": BOX, "legend": False},   # (5, 7)
            {"key": "KC_Q", "drawing": BOX}])                                     # a keycode one
        self.assertEqual(len(files), 1)
        conv = key_images.KeyImageConverter(DeviceSettings())
        self.assertTrue(conv.open(files[0]))
        self.assertEqual(set(conv.extract_overlays(Modifier.NO_MOD)), {0, 5 * 8 + 7})
        self.assertIsNone(conv.extract_overlays(Modifier.CTRL))
        self.assertEqual(conv.no_legend, {(key_images.KEY_POSITION, 47)})

    def test_an_alias_is_stored_by_its_canonical_name(self):
        self._star([{"key": "L:9.4", "follow": "key", "drawing": BOX}])
        self.assertEqual(uo.load_set("*", self.root)["bindings"][0]["key"], "R:8.4")

    def test_follow_key_is_for_the_star_set_only_and_takes_no_mods(self):
        with self.assertRaises(uo.UserOverlayError):
            uo.save_set("blender", [{"key": "L:1.1", "follow": "key", "drawing": BOX}], self.root)
        with self.assertRaises(uo.UserOverlayError):
            uo.save_set("*", [{"key": "L:1.1", "follow": "key", "drawing": BOX,
                               "mods": ["CTRL"]}], self.root)
        with self.assertRaises(uo.UserOverlayError):
            uo.save_set("*", [{"key": "L:5.5", "follow": "key", "drawing": BOX}], self.root)

    def test_a_key_binding_and_a_keycode_binding_do_not_replace_each_other(self):
        self._star([{"key": "L:1.1", "follow": "key", "drawing": BOX},
                    {"key": "KC_ESCAPE", "drawing": BOX}])
        self.assertEqual(len(uo.load_set("*", self.root)["bindings"]), 2)
        self.assertTrue(uo.remove_binding("*", "L:1.1", root=self.root))
        self.assertEqual(uo.load_set("*", self.root)["bindings"][0]["key"], "KC_ESCAPE")
        self.assertFalse(uo.remove_binding("*", "L:1.1", root=self.root))

    def test_mapping_from(self):
        self.assertEqual(key_images.mapping_from(0), 1456)
        self.assertEqual(key_images.mapping_from(79), 1535)
        for bad in (-1, 80):
            with self.assertRaises(ValueError):
                key_images.mapping_from(bad)


class SendTest(unittest.TestCase):
    """The send path against the emulated keyboard, both sides of the v40 gate."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="polykybd-keys-")
        self.addCleanup(shutil.rmtree, self.root, True)
        uo.save_set("*", [{"key": "L:1.1", "follow": "key", "drawing": BOX, "legend": False},
                          {"key": "KC_Q", "drawing": BOX}], self.root)
        self.files = uo.star_files(self.root)

    def _send(self, protocol):
        kb = PolyKybdMock(DeviceSettings(), protocol=protocol)
        with mock.patch("time.sleep", lambda s: None):
            self.assertTrue(kb.send_overlays_mru(self.files, OverlayMRUCache(600),
                                                 threading.Event()))
        return kb

    def test_v40_maps_the_key_image_to_its_physical_from(self):
        kb = self._send(KEY_OVERLAY_MIN_PROTOCOL)
        mapping = kb.firmware.sim._mapping
        self.assertIn(key_images.mapping_from(0), mapping)
        self.assertIn(key_images.mapping_from(0), kb.firmware.no_legend_positions)
        self.assertEqual(kb.firmware.refused, [])

    def test_older_firmware_gets_no_key_image_and_refuses_nothing(self):
        kb = self._send(KEY_OVERLAY_MIN_PROTOCOL - 1)
        self.assertFalse([f for f in kb.firmware.sim._mapping
                          if f >= key_images.KEY_OVERLAY_BASE])
        self.assertEqual(kb.firmware.refused, [])
        # The keycode drawing still goes out.
        self.assertTrue(kb.firmware.sim._mapping)


if __name__ == "__main__":
    unittest.main()
