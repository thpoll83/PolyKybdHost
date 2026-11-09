"""The connect-time font-pack check waits while Eden owns the keycaps, through the
real reconnect probe and connect path on the mock keyboard (protocol 28)."""
import threading
import unittest
import unittest.mock as mock

try:
    from polyhost.core.poly_core import PolyCore
    from polyhost.device import hid_fontpack
    from polyhost.settings import PolySettings
    _HAVE_CORE = True
except Exception:   # noqa: BLE001 - heavy optional deps
    _HAVE_CORE = False


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class EdenHoldThroughTheProbeTest(unittest.TestCase):

    def setUp(self):
        real_get = PolySettings.get
        values = {"dev_mock_primary": True, "dev_mock_protocol": 0,
                  "fontpack_auto_flash": True}

        def get(settings, name):
            return values[name] if name in values else real_get(settings, name)

        for p in (mock.patch.object(PolySettings, "get", get),
                  mock.patch.object(PolySettings, "save", lambda *a, **k: True)):
            p.start()
            self.addCleanup(p.stop)
        self.core = PolyCore(mock.MagicMock(), start_worker=False)
        self.jobs = []
        self.core.worker.submit = lambda name, fn, **kw: self.jobs.append(name)
        self.fw = self.core.keeb.firmware
        self.fw.bundle_versions.pop(0, None)          # one bundle is stale

    def _probe(self):
        snap = self.core._reconnect_probe(threading.Event())
        if snap is not None and (snap["state_changed"] or snap["fresh_boot"]):
            self.core.apply_reconnect(snap)

    def _checks(self):
        return [j for j in self.jobs if j == "fontpack_autocheck"]

    def test_the_intro_holds_the_check_until_it_ends(self):
        self.fw.anim_state = hid_fontpack.ANIM_INTRO
        self._probe()
        self.assertEqual(self.core.keeb.anim_state, hid_fontpack.ANIM_INTRO)
        self.assertTrue(self.core._fontpack_check_held)
        self._probe()
        self.assertEqual(self._checks(), [], "still in the intro")
        self.fw.anim_state = hid_fontpack.ANIM_NONE
        self._probe()
        self.assertEqual(self._checks(), ["fontpack_autocheck"])
        self.assertFalse(self.core._fontpack_check_held)

    def test_a_reboot_during_the_hold_drops_it_and_the_connect_decides(self):
        self.fw.anim_state = hid_fontpack.ANIM_IDLE
        self._probe()
        self.assertTrue(self.core._fontpack_check_held)
        self.fw.anim_state = hid_fontpack.ANIM_NONE
        self.fw.fresh_boot = True                     # rebooted between two probes
        snap = self.core._reconnect_probe(threading.Event())
        self.assertTrue(snap["fresh_boot"])
        self.assertFalse(self.core._fontpack_check_held)
        self.assertEqual(self._checks(), [], "the probe itself queued nothing")
        self.core.apply_reconnect(snap)
        self.assertEqual(self._checks(), ["fontpack_autocheck"], "the connect queued it")


if __name__ == "__main__":
    unittest.main()
