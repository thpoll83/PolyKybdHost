"""The core's device traffic against every keyboard generation it connects to.

The device sweep (tests/device/protocol_gate_sweep_test.py) holds each
`PolyKybd` method to its gate. Some gates live in the CALLER instead -- the
brightness flags are the core's decision -- and some core paths reach the
device without a `PolyKybd` method at all (font-pack status reads `keeb.hid`
directly). This runs a real `PolyCore` with the mock as its only keyboard
(`dev_mock_primary`) at every protocol, through a fresh connect, both
brightness modes and every core method that touches the keyboard, and asserts
the emulated firmware never received a command it would not have understood.

⚠️ A new core method that touches `self.keeb` fails
test_every_device_method_is_swept until it is in CORE_CALLS (or EXEMPT, with
the reason).
"""
import ast
import inspect
import threading
import unittest
from unittest import mock

from polyhost._version import __protocol__
from polyhost.core.poly_core import PolyCore
from polyhost.device.command_ids import IdleTimeout
from polyhost.device.poly_kybd import MIN_SUPPORTED_PROTOCOL
from polyhost.settings import PolySettings

CORE_CALLS = {
    "activate_bootloader": (), "set_handedness": (True,),
    "clear_crash_record": (), "get_crash_record": (0,),
    "fontpack_bundle_status": (),
    "get_fw_version": (),
    "apply_staged_firmware": (),
    "get_glyph_script": (), "set_glyph_script": (0,),
    "get_glyph_size": (), "set_glyph_size": (0,),
    "get_idle_style": (), "set_idle_style": (0,),
    "get_idle_timeout": (), "set_idle_timeout": (IdleTimeout.MIN_2.value,),
    "set_idle": (True,),
    "keymap_buffer": (), "keymap_default_layer": (), "keymap_layer_count": (),
    "keymap_layer_names": (), "keymap_set": (0, 0, 0, 4), "reset_dynamic_keymap": (),
    "list_languages": (), "set_language": ("enUS",),
    "macro_list": (),
    "refresh_unicode_mode": (),
    "replay_startup_anim": (),
    "reset_overlay_buffers": (), "reset_overlay_mapping": (), "reset_overlay_usage": (),
    "reset_overlays": (), "set_all_overlay_usage": (), "send_overlay_mapping": ({0: 1},),
    "enable_overlays": (), "disable_overlays": (),
    "save_mru": (),
    "set_brightness": (10,),
    "mock_keycaps": (0,),
}

# The font-pack and firmware-update transports are dispatched independently of
# the protocol version ON PURPOSE (add-gated-hid-command: "NOT for the overlay/
# font-pack bulk transports"): an old keyboard NACKs the BEGIN or STATUS and the
# user gets a plain error, nothing bricks. tests/device/mock_fault_test.py drives
# them against the emulator instead.
_TRANSPORT = "bulk transport, ungated by design; see mock_fault_test.py"

EXEMPT = {
    "get_fontpack_status": _TRANSPORT,
    "flash_fontpack": _TRANSPORT,
    "flash_firmware": _TRANSPORT,
    "install_doompack": _TRANSPORT,
    "install_doomwad": _TRANSPORT,
    "apply_reconnect": "driven by every scenario below",
    "get_status": "reads cached state only",
    "macro_set": "whole-buffer read-modify-write over the macro accessors, which are swept",
    "set_newer_firmware_policy": "reads the cached protocol only",
    "shutdown": "tears the core down",
    "submit_overlay_cmd": "queues _overlay_cmd_job: enable/disable, swept directly",
    "tick_window_tracking": "the window loop; its overlay sends are covered by the device sweep",
}


def _device_methods():
    """Public PolyCore methods whose source mentions self.keeb."""
    names = []
    for name, fn in inspect.getmembers(PolyCore, inspect.isfunction):
        if name.startswith("_"):
            continue
        try:
            tree = ast.parse(inspect.getsource(fn).strip())
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and node.attr == "keeb"
                    and isinstance(node.value, ast.Name) and node.value.id == "self"):
                names.append(name)
                break
    return sorted(names)


class CoreProtocolSweepTest(unittest.TestCase):

    def _core(self, protocol, **overrides):
        real_get = PolySettings.get
        values = {"dev_mock_primary": True, "dev_mock_protocol": protocol,
                  "unicode_send_composition_mode": True, **overrides}

        def get(settings, name):
            return values[name] if name in values else real_get(settings, name)

        patches = [mock.patch.object(PolySettings, "get", get),
                   mock.patch.object(PolySettings, "save", lambda *a, **k: True),
                   mock.patch.object(PolyCore, "_compute_daylight_value", lambda self: 20)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        core = PolyCore(mock.MagicMock(), start_worker=False)
        core.worker.start()
        self.addCleanup(core.shutdown)
        return core, values

    @staticmethod
    def _settle(core):
        core.worker.run_sync("barrier", lambda c: None, timeout=30)

    def test_every_device_method_is_swept(self):
        missing = [n for n in _device_methods() if n not in CORE_CALLS and n not in EXEMPT]
        self.assertEqual(missing, [], "add these PolyCore methods to CORE_CALLS")

    def test_the_core_sends_nothing_a_keyboard_cannot_take(self):
        refused = {}
        for protocol in range(MIN_SUPPORTED_PROTOCOL, __protocol__ + 1):
            with self.subTest(protocol=protocol):
                core, values = self._core(protocol, brightness_set_daylight_dependent=True)
                snapshot = core._reconnect_probe(threading.Event())
                core.apply_reconnect(snapshot)
                self._settle(core)
                self.assertTrue(core.connected, f"v{protocol} did not connect")
                values["brightness_set_daylight_dependent"] = False
                core.refresh_daylight_brightness()
                self._settle(core)
                for name, args in CORE_CALLS.items():
                    getattr(core, name)(*args)
                self._settle(core)
                for r in core.keeb.firmware.refused:
                    refused.setdefault(f"v{protocol}", []).append(r.reason)
        self.assertEqual(refused, {})


if __name__ == "__main__":
    unittest.main()
