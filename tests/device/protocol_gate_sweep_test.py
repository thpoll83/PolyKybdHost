"""Every PolyKybd command against every keyboard generation the host connects to.

The rule this enforces is the one CLAUDE.md says "has been forgotten twice":
every device-facing command must be gated on the keyboard's protocol. An
ungated command connects fine and then NACKs at runtime on an older board.

How: a real `PolyKybd` talks to `MockFirmware` (device/mock_firmware.py), which
answers exactly the commands firmware of a given PROTOCOL_VERSION knew and
records anything else in `refused`. For each protocol from
MIN_SUPPORTED_PROTOCOL to this host's newest, every public method runs with
the arguments in CALLS; afterwards nothing may have been refused.

⚠️ A new public method on PolyKybd FAILS this test until it has an entry in
CALLS (or NO_DEVICE_IO). That is deliberate: the entry is where its author
decides which wire forms the method can produce.
"""
import threading
import unittest

import numpy as np

from polyhost._version import __protocol__
from polyhost.device import synthetic_overlay as syn
from polyhost.device.command_ids import Cmd, GlyphScript, GlyphSize, IdleStyle, IdleTimeout, OsType
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.mock_firmware import (CMD_MIN_PROTOCOL, RETIRED_CMDS, MockFirmware,
                                           MockHidHelper, command_known)
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.overlay_data import OverlayData
from polyhost.device.poly_kybd import MIN_SUPPORTED_PROTOCOL, PolyKybd
from polyhost.input.unicode_input import InputMethod


class _Settings:
    def get(self, name):
        return {"max_hid_message_before_delay": 1 << 30,
                "delay_time_after_max_hid_messages": 0,
                "hid_reconnect_retries": 1}.get(name)


def _overlay(ds, seed=0):
    rng = np.random.default_rng(seed)
    image = np.zeros((40, 72), dtype=bool)
    image[8:30, 10:60] = rng.random((22, 50)) > 0.5
    return OverlayData(ds, image)


def _send_mru(kb):
    """An app switch carrying a GUI-combo variant (protocol 12+ only)."""
    ds = kb.device_settings
    conv = syn.SyntheticConverter({
        Modifier.NO_MOD: {KeyCode.KC_A.value: _overlay(ds, 1)},
        Modifier.GUI_CTRL: {KeyCode.KC_B.value: _overlay(ds, 2)},
    })
    return kb.send_overlays_mru(["@sweep"], OverlayMRUCache(600), threading.Event(),
                                synthetic={"@sweep": conv})


def _each_encoding(kb):
    ds = kb.device_settings
    ov = {KeyCode.KC_C.value: _overlay(ds, 3)}
    kb.send_overlay_for_keycode(KeyCode.KC_C.value, Modifier.NO_MOD, ov)
    kb.send_overlay_for_keycode_compressed(KeyCode.KC_C.value, Modifier.NO_MOD, ov)
    kb.send_overlay_roi_for_keycode(KeyCode.KC_C.value, Modifier.NO_MOD, ov, False)
    kb.send_overlay_roi_for_keycode(KeyCode.KC_C.value, Modifier.NO_MOD, ov, True)
    return kb.send_smallest_overlay(KeyCode.KC_C.value, Modifier.NO_MOD, ov)


# method -> list of argument tuples, or a callable(kb) for a whole scenario.
CALLS = {
    "connect": [()],
    "query_id": [()],
    "query_version_info": [()],
    "pop_fresh_boot": [()],
    "get_name": [()], "get_sw_version": [()], "get_sw_version_number": [()],
    "get_hw_version": [()], "get_protocol_version": [()],
    "read_serial": [()], "get_console_output": [()],
    "reset_overlay_mapping": [()], "set_all_overlay_usage": [()],
    "set_mirror_overlays": [(True,), (False,)],
    "reset_overlays_and_usage": [()], "reset_overlay_mapping_and_usage": [()],
    "prepare_for_mru_send": [()], "reset_overlay_usage": [()], "reset_overlays": [()],
    "enable_overlays": [()], "disable_overlays": [()],
    "set_unicode_mode": [(InputMethod.Linux,), (InputMethod.Linux, False)],
    "set_brightness": [(10,)],
    "press_and_release_key": [(0x04, 0)],
    "press_key": [(0x04,)], "release_key": [(0x04,)],
    "activate_bootloader": [()],
    "reboot": [()],
    "set_idle": [(True,), (False,)],
    "set_idle_style": [(list(IdleStyle)[0],)], "get_idle_style": [()],
    "set_idle_timeout": [(IdleTimeout.MIN_2,)], "get_idle_timeout": [()],
    "set_glyph_script": [(list(GlyphScript)[0],)], "get_glyph_script": [()],
    "set_glyph_size": [(list(GlyphSize)[0],)], "get_glyph_size": [()],
    "get_crash_record": [(0,), (1,)], "clear_crash_record": [()],
    "get_layer_names": [()],
    "get_macro_info": [()], "read_macro_buffer": [(64,)],
    "write_macro_buffer": [(b"hi\x00",)], "get_macro_look": [(0,)],
    "set_macro_look": [(0, "Hi")],
    "replay_startup_anim": [()],
    "set_os": [(list(OsType)[0],)], "get_os": [()],
    "save_mru": [()],
    "set_handedness": [(True,)],
    "query_current_lang": [()],
    "enumerate_lang": [()],
    "get_lang_list": [()], "get_current_lang": [()],
    "change_language": [("enUS",)],
    "send_overlay_mapping": [({0: 1},), ({0: 1, 1000: 2},), ({0: 1}, True, True)],
    "send_overlays": [(["/nonexistent/overlay.png"],)],
    "send_overlays_mru": _send_mru,
    "send_smallest_overlay": _each_encoding,
    "send_overlay_for_keycode": _each_encoding,
    "send_overlay_for_keycode_compressed": _each_encoding,
    "send_overlay_roi_for_keycode": _each_encoding,
    "execute_commands": [(["wait 0", "press 0x04", "release 0x04"],)],
    "get_default_layer": [()], "get_dynamic_keycode": [(0, 0, 0)],
    "get_dynamic_layer_count": [()], "reset_dynamic_keymap": [()],
    "set_dynamic_keycode": [(0, 0, 0, 0x04)], "get_dynamic_buffer": [()],
}

# Forms whose gate lives in the CALLER, with where it is. They run only where
# the caller would send them; the core sweep (tests/core/core_protocol_sweep_
# test.py) is what holds the caller to it.
CALLER_GATED = {
    "set_brightness": ("brightness_flags", [(10, 1), (0, 4)],
                       "PolyCore._brightness_flags_supported"),
}

# No device I/O at all: nothing to sweep.
NO_DEVICE_IO = {"supports", "capabilities"}


def _keyboard(protocol):
    fw = MockFirmware(protocol, languages=["enUS", "deAT"])
    kb = PolyKybd(DeviceSettings(), _Settings())
    kb.hid = MockHidHelper(fw)
    kb.protocol_version = protocol          # what a connect leaves behind
    kb.all_languages = ["enUS", "deAT"]
    return kb, fw


def _public_methods():
    return sorted(n for n in dir(PolyKybd)
                  if not n.startswith("_") and callable(getattr(PolyKybd, n)))


class CommandTableTest(unittest.TestCase):
    def test_every_command_id_is_classified(self):
        unclassified = [c.name for c in Cmd
                        if c.value not in CMD_MIN_PROTOCOL and c.value not in RETIRED_CMDS]
        self.assertEqual(unclassified, [],
                         "add each new Cmd to mock_firmware.CMD_MIN_PROTOCOL with the "
                         "protocol that introduced it")

    def test_retired_language_list_is_refused_from_v2(self):
        self.assertTrue(command_known(Cmd.GET_LANG_LIST.value, 1))
        self.assertFalse(command_known(Cmd.GET_LANG_LIST.value, 2))


class ProtocolGateSweepTest(unittest.TestCase):

    def test_every_public_method_has_a_sweep_entry(self):
        missing = [n for n in _public_methods()
                   if n not in CALLS and n not in CALLER_GATED and n not in NO_DEVICE_IO]
        self.assertEqual(missing, [],
                         "add these PolyKybd methods to CALLS so the protocol sweep "
                         "exercises every wire form they can produce")

    def test_no_command_reaches_a_keyboard_too_old_for_it(self):
        refused = {}
        for protocol in range(MIN_SUPPORTED_PROTOCOL, __protocol__ + 1):
            for name in _public_methods():
                if name in NO_DEVICE_IO:
                    continue
                kb, fw = _keyboard(protocol)
                method = getattr(kb, name)
                if name in CALLER_GATED:
                    feature, forms, _ = CALLER_GATED[name]
                    calls = list(CALLS.get(name, [()]))
                    if kb.supports(feature):
                        calls += forms
                else:
                    calls = CALLS[name]
                try:
                    if callable(calls):
                        calls(kb)
                    else:
                        for args in calls:
                            method(*args)
                except Exception as e:   # noqa: BLE001 -- a crash is a finding too
                    refused.setdefault(name, []).append(f"v{protocol}: raised {e!r}")
                for r in fw.refused:
                    refused.setdefault(name, []).append(f"v{protocol}: {r.reason}")
        self.assertEqual(refused, {})

    def test_the_sweep_can_see_a_missing_gate(self):
        # Positive control: an ungated GLYPH_SIZE on a v12 keyboard is refused.
        from polyhost.device.cmd_composer import compose_cmd
        kb, fw = _keyboard(12)
        kb.hid.send_and_read_validate(compose_cmd(Cmd.GLYPH_SIZE, 0xFF))
        self.assertEqual(len(fw.refused), 1)
        self.assertIn("needs protocol 13", fw.refused[0].reason)

    def test_caller_gated_forms_really_need_their_gate(self):
        # If a caller-gated form were harmless below its protocol, the entry
        # would be hiding nothing and should go.
        for name, (feature, forms, _where) in CALLER_GATED.items():
            from polyhost.device.poly_kybd import FEATURE_MIN_PROTOCOL
            kb, fw = _keyboard(FEATURE_MIN_PROTOCOL[feature] - 1)
            for args in forms:
                getattr(kb, name)(*args)
            self.assertTrue(fw.refused, name)


if __name__ == "__main__":
    unittest.main()
