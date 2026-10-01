"""PolyCore.mock_keycaps: what the board view reads, primary or secondary mock."""
import base64
import threading
import unittest
import unittest.mock as mock

import numpy as np

from polyhost.core.poly_core import PolyCore
from polyhost.device import synthetic_overlay as syn
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_data import OverlayData
from polyhost.settings import PolySettings


class MockKeycapsTest(unittest.TestCase):

    def _core(self, **values):
        real_get = PolySettings.get

        def get(settings, name):
            return values[name] if name in values else real_get(settings, name)

        for p in (mock.patch.object(PolySettings, "get", get),
                  mock.patch.object(PolySettings, "save", lambda *a, **k: True)):
            p.start()
            self.addCleanup(p.stop)
        core = PolyCore(mock.MagicMock(), start_worker=False)
        core.worker.start()
        self.addCleanup(core.shutdown)
        return core

    @staticmethod
    def _send(device, cache, shift_image):
        conv = syn.SyntheticConverter({Modifier.SHIFT: {
            KeyCode.KC_Q.value: OverlayData(DeviceSettings(), shift_image)}})
        assert device.send_overlays_mru(["@t"], cache, threading.Event(), synthetic={"@t": conv})

    def test_without_a_mock_it_says_how_to_get_one(self):
        core = self._core(dev_mock_primary=False, dev_mock_enabled=False)
        ok, msg = core.mock_keycaps()
        self.assertFalse(ok)
        self.assertIn("dev_mock_primary", msg)

    def test_the_primary_mock_reports_its_keycaps_per_modifier(self):
        core = self._core(dev_mock_primary=True, dev_mock_protocol=19)
        image = np.zeros((40, 72), dtype=bool)
        image[10:30, 20:50] = True
        self._send(core.keeb, core.device_mgr.primary.cache, image)

        ok, plain = core.mock_keycaps(Modifier.NO_MOD.value)
        self.assertTrue(ok)
        self.assertEqual(plain["images"], {})
        ok, shifted = core.mock_keycaps(Modifier.SHIFT.value)
        self.assertTrue(shifted["primary"])
        self.assertEqual(shifted["protocol"], 19)
        self.assertTrue(shifted["overlays_enabled"])
        packed = base64.b64decode(shifted["images"][str(KeyCode.KC_Q.value)])
        self.assertEqual(packed, np.packbits(image).tobytes())
        # The board seeds layer 0 from the firmware keymap: ESC at (0, 0).
        self.assertEqual(shifted["base_layer"]["0,0"], KeyCode.KC_ESCAPE.value)

    def test_the_secondary_mock_is_found_too(self):
        core = self._core(dev_mock_primary=False, dev_mock_enabled=True)
        ok, payload = core.mock_keycaps()
        self.assertTrue(ok)
        self.assertFalse(payload["primary"])


if __name__ == "__main__":
    unittest.main()
