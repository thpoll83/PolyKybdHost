"""PolyCore._overlay_cmd_job — device enable/disable + failure re-arm.

The redundant-command guard in OverlayHandler advances ``overlays_enabled``
optimistically, so ``_overlay_cmd_job`` must re-arm the handler (revert to the
pre-command state) whenever the device call FAILS — whether it returns
``(False, …)`` or RAISES — so the next poll retries instead of the guard
suppressing it. Exercised by calling the method with a stand-in ``self`` (no
full PolyCore / HID stack needed)."""
import logging
import types
import unittest

from polyhost.core.poly_core import PolyCore
from polyhost.handler.common import OverlayCommand


class _Cancel:
    def is_set(self):
        return False


class _Dev:
    def __init__(self, result=(True, "."), raises=False):
        self.result = result
        self.raises = raises
        self.disable_calls = 0
        self.enable_calls = 0

    def disable_overlays(self):
        self.disable_calls += 1
        if self.raises:
            raise RuntimeError("hid write failed")
        return self.result

    def enable_overlays(self):
        self.enable_calls += 1
        if self.raises:
            raise RuntimeError("hid write failed")
        return self.result


class _Handler:
    def __init__(self, enabled):
        self.overlays_enabled = enabled

    def note_overlay_state(self, enabled):
        self.overlays_enabled = enabled


def _core(entries, handler):
    return types.SimpleNamespace(
        device_mgr=types.SimpleNamespace(all_entries=entries),
        overlay_handler=handler,
        log=logging.getLogger("test"),
        _last_overlay_activity=0.0,
    )


class TestOverlayCmdJob(unittest.TestCase):
    def _run(self, cmd, dev, handler):
        core = _core([types.SimpleNamespace(device=dev)], handler)
        PolyCore._overlay_cmd_job(core, cmd, _Cancel())
        return core

    def test_success_leaves_state(self):
        # Handler already set overlays_enabled=False for the DISABLE; a
        # successful device call leaves it as-is (no re-arm).
        h = _Handler(enabled=False)
        self._run(OverlayCommand.DISABLE, _Dev(result=(True, ".")), h)
        self.assertFalse(h.overlays_enabled)

    def test_failed_disable_result_rearms(self):
        h = _Handler(enabled=False)
        self._run(OverlayCommand.DISABLE, _Dev(result=(False, "NACK")), h)
        self.assertTrue(h.overlays_enabled)  # re-armed to "enabled"

    def test_raising_disable_rearms(self):
        h = _Handler(enabled=False)
        dev = _Dev(raises=True)
        self._run(OverlayCommand.DISABLE, dev, h)
        self.assertTrue(h.overlays_enabled)   # exception treated as failure
        self.assertEqual(dev.disable_calls, 1)

    def test_raising_enable_rearms(self):
        h = _Handler(enabled=True)
        self._run(OverlayCommand.ENABLE, _Dev(raises=True), h)
        self.assertFalse(h.overlays_enabled)  # re-armed to "disabled"

    def test_raise_continues_to_other_devices(self):
        # A raising first device must not stop the second being attempted.
        bad, good = _Dev(raises=True), _Dev(result=(True, "."))
        core = _core(
            [types.SimpleNamespace(device=bad), types.SimpleNamespace(device=good)],
            _Handler(enabled=False),
        )
        PolyCore._overlay_cmd_job(core, OverlayCommand.DISABLE, _Cancel())
        self.assertEqual(good.disable_calls, 1)          # reached despite bad raising
        self.assertTrue(core.overlay_handler.overlays_enabled)  # re-armed


if __name__ == "__main__":
    unittest.main()
