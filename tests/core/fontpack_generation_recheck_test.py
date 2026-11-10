"""The font-pack check runs again when the keyboard's version block changes during
a session, through the real reconnect probe on the mock keyboard.

The connect-time check reads GET_ID's version block once. Until the master has read
the slave's versions the block is the master's alone, so a slave that missed a
bundle flash was found only at the next connect. The probe now re-runs the check
when the 'G' counter moved AND the block differs from the one last checked."""
import threading
import unittest
import unittest.mock as mock

try:
    from polyhost.core.poly_core import PolyCore
    from polyhost.settings import PolySettings
    _HAVE_CORE = True
except Exception:   # noqa: BLE001 - heavy optional deps
    _HAVE_CORE = False


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class FontpackRecheckOnGenerationTest(unittest.TestCase):

    def setUp(self):
        real_get = PolySettings.get
        self.values = {"dev_mock_primary": True, "dev_mock_protocol": 0,
                       "fontpack_auto_flash": True}

        def get(settings, name):
            return self.values[name] if name in self.values else real_get(settings, name)

        for p in (mock.patch.object(PolySettings, "get", get),
                  mock.patch.object(PolySettings, "save", lambda *a, **k: True)):
            p.start()
            self.addCleanup(p.stop)
        self.core = PolyCore(mock.MagicMock(), start_worker=False)
        self.jobs = []
        self.core.worker.submit = lambda name, fn, **kw: self.jobs.append(name)
        self.fw = self.core.keeb.firmware
        self._probe()                                  # connect: the first check
        self.assertEqual(self._checks(), ["fontpack_autocheck"])
        self._probe()                                  # one steady probe
        self.jobs.clear()

    def _probe(self):
        snap = self.core._reconnect_probe(threading.Event())
        if snap is not None and (snap["state_changed"] or snap["fresh_boot"]):
            self.core.apply_reconnect(snap)

    def _checks(self):
        return [j for j in self.jobs if j in ("fontpack_autocheck", "fontpack_stale_notice")]

    def test_a_changed_version_block_with_a_new_generation_checks_again(self):
        self.fw.bundle_versions[0] = self.fw.bundle_versions.get(0, 0) + 1
        self.fw.state_generation += 1
        self._probe()
        self.assertEqual(self._checks(), ["fontpack_autocheck"])
        self._probe()
        self.assertEqual(self._checks(), ["fontpack_autocheck"], "once per change")

    def test_a_new_generation_with_the_same_block_does_not_check(self):
        self.fw.state_generation += 1                  # e.g. a keymap edit
        self._probe()
        self.assertEqual(self._checks(), [])

    def test_a_changed_block_without_a_new_generation_does_not_check(self):
        self.fw.bundle_versions[0] = self.fw.bundle_versions.get(0, 0) + 1
        self._probe()
        self.assertEqual(self._checks(), [], "the counter is the trigger")

    def test_no_recheck_while_a_flash_runs(self):
        self.core._fontpack_flash_in_progress = True
        self.fw.bundle_versions[0] = self.fw.bundle_versions.get(0, 0) + 1
        self.fw.state_generation += 1
        self._probe()
        self.assertEqual(self._checks(), [])

    def test_with_auto_flash_off_the_recheck_shows_the_notice_instead(self):
        self.values["fontpack_auto_flash"] = False
        self.fw.bundle_versions[0] = self.fw.bundle_versions.get(0, 0) + 1
        self.fw.state_generation += 1
        self._probe()
        self.assertEqual(self._checks(), ["fontpack_stale_notice"])


if __name__ == "__main__":
    unittest.main()
