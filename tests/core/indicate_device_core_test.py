"""PolyCore.indicate_device: six toggles, and on a failed toggle the RGB matrix is
switched back to its state before the blink (never by a blind toggle)."""
import types
import unittest

from polyhost.core.poly_core import PolyCore


class _Keeb:
    def __init__(self, fail_at=None, applied=True):
        self.enabled = True
        self.fail_at, self.applied = fail_at, applied
        self.calls = []

    def get_rgb_matrix(self):
        return True, {"enabled": self.enabled}

    def indicate_device(self, i):
        self.calls.append(("indicate", i))
        if i == self.fail_at:
            if self.applied:
                self.enabled = not self.enabled     # applied, reply lost
            return False, "refused"
        self.enabled = not self.enabled
        return True, "ok"

    def set_rgb_matrix(self, **kw):
        self.calls.append(("set", kw))
        self.enabled = kw["enabled"]
        return True, "ok"


def _core(keeb, safe_mode=False):
    core = types.SimpleNamespace(keeb=keeb, INDICATE_TOGGLES=6, INDICATE_INTERVAL_S=0,
                                 safe_mode=safe_mode)
    core._device_call = lambda name, fn: fn(None)
    return core


class IndicateTest(unittest.TestCase):
    def test_six_toggles_end_as_started(self):
        keeb = _Keeb()
        self.assertEqual(PolyCore.indicate_device(_core(keeb)), (True, "ok"))
        self.assertEqual([c for c in keeb.calls if c[0] == "indicate"],
                         [("indicate", i) for i in range(6)])
        self.assertTrue(keeb.enabled)

    def test_an_applied_toggle_with_a_lost_reply_is_switched_back(self):
        keeb = _Keeb(fail_at=1, applied=True)        # toggles 0 and 1 applied: back on
        ok, _ = PolyCore.indicate_device(_core(keeb))
        self.assertFalse(ok)
        self.assertTrue(keeb.enabled)
        self.assertNotIn("set", [c[0] for c in keeb.calls])   # already as before

    def test_a_refused_toggle_leaves_the_state_restored(self):
        keeb = _Keeb(fail_at=1, applied=False)       # only toggle 0 applied: off
        ok, _ = PolyCore.indicate_device(_core(keeb))
        self.assertFalse(ok)
        self.assertTrue(keeb.enabled)
        self.assertIn(("set", {"enabled": True}), keeb.calls)


class SafeModeTest(unittest.TestCase):
    def test_every_via_call_is_refused_without_device_io(self):
        from polyhost.core.poly_core import SAFE_MODE_REFUSAL
        keeb = _Keeb()
        core = _core(keeb, safe_mode=True)
        for call in (lambda: PolyCore.get_rgb_matrix(core),
                     lambda: PolyCore.set_rgb_matrix(core, {"enabled": False}),
                     lambda: PolyCore.get_uptime_ms(core),
                     lambda: PolyCore.indicate_device(core),
                     lambda: PolyCore.get_switch_matrix(core)):
            self.assertEqual(call(), (False, SAFE_MODE_REFUSAL))
        self.assertEqual(keeb.calls, [])
        self.assertTrue(keeb.enabled)


if __name__ == "__main__":
    unittest.main()
