"""Tests for PolyCore.refresh_unicode_mode.

The unicode input mode is normally pushed once per connect, so installing (or
quitting) WinCompose mid-session needs this explicit re-push — it backs both the
tray's post-install refresh and `polyctl unicode-mode`.
"""
import types
import unittest
from unittest.mock import patch

from polyhost.input.unicode_input import InputMethod

try:
    from polyhost.core.poly_core import PolyCore
    _HAVE_CORE = True
except Exception:   # noqa: BLE001 — heavy optional deps (numpy/PIL/pvlib/…)
    _HAVE_CORE = False


def _fake_core(send_mode=True, device_result=(True, "ok")):
    """Minimal stand-in exposing exactly what refresh_unicode_mode touches."""
    settings = {"unicode_send_composition_mode": send_mode}
    calls = []

    def _device_call(name, fn):
        calls.append(name)
        return device_result

    core = types.SimpleNamespace(
        poly_settings=types.SimpleNamespace(get=lambda k: settings[k]),
        keeb=types.SimpleNamespace(set_unicode_mode=lambda m: (True, "ok")),
        log=types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
        _device_call=_device_call,
    )
    core._calls = calls
    return core


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class RefreshUnicodeModeTest(unittest.TestCase):

    def test_pushes_the_detected_mode(self):
        core = _fake_core()
        with patch("polyhost.input.unicode_input.get_input_method",
                   return_value=InputMethod.WinCompose):
            ok, payload = PolyCore.refresh_unicode_mode(core)
        self.assertTrue(ok)
        self.assertEqual(payload, {"mode": "WinCompose"})
        self.assertEqual(core._calls, ["set_unicode_mode"])

    def test_respects_the_disabled_setting(self):
        """Users who turned the composition-mode push off must not get one here."""
        core = _fake_core(send_mode=False)
        ok, msg = PolyCore.refresh_unicode_mode(core)
        self.assertFalse(ok)
        self.assertIn("disabled", msg)
        self.assertEqual(core._calls, [])

    def test_device_failure_is_reported_verbatim(self):
        core = _fake_core(device_result=(False, "no PolyKybd present"))
        with patch("polyhost.input.unicode_input.get_input_method",
                   return_value=InputMethod.Windows):
            ok, msg = PolyCore.refresh_unicode_mode(core)
        self.assertFalse(ok)
        self.assertEqual(msg, "no PolyKybd present")


if __name__ == "__main__":
    unittest.main()
