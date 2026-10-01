"""MockFirmware: does the emulated keyboard decode what the real host sends?

The real `PolyKybd` writes every report here; the assertions read the emulated
keyboard back. So a pass means the host's encoder and the emulator's decoder
agree -- and the decoder is a copy of the firmware's (fill_overlay.c), not of
the encoder, which is what keeps this from being a round trip through one
person's idea of the format.
"""
import threading
import unittest

import numpy as np

from polyhost.device import synthetic_overlay as syn
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.hid_fontpack import parse_id_state_generation, parse_id_version_block
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.mock_firmware import MockFirmware, MockHidHelper
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.overlay_data import OverlayData
from polyhost.device.poly_kybd import PolyKybd


class _Settings:
    def get(self, name):
        return {"max_hid_message_before_delay": 1 << 30,
                "delay_time_after_max_hid_messages": 0}.get(name)


def _keyboard(protocol=21, **kw):
    fw = MockFirmware(protocol, **kw)
    kb = PolyKybd(DeviceSettings(), _Settings())
    kb.hid = MockHidHelper(fw)
    kb.protocol_version = protocol
    kb.fontpack_bundle_versions = fw.reported_bundle_versions()
    return kb, fw


def _image(kind, seed=0):
    rng = np.random.default_rng(seed)
    a = np.zeros((40, 72), dtype=bool)
    if kind == "noise":
        a[:] = rng.random((40, 72)) > 0.5
    elif kind == "small":
        a[12:24, 30:44] = rng.random((12, 14)) > 0.4
    elif kind == "stripe":
        a[::3, :] = True
    elif kind == "corner":
        a[0, 0] = a[39, 71] = True
    return a


def _send(kb, images, cache=None, name="@src"):
    conv = syn.SyntheticConverter({Modifier.NO_MOD: {
        kc: OverlayData(kb.device_settings, img) for kc, img in images.items()}})
    ok = kb.send_overlays_mru([name], cache or OverlayMRUCache(600), threading.Event(),
                              synthetic={name: conv})
    assert ok
    return conv


class EncodingTest(unittest.TestCase):
    """Each of the five encodings decodes back to the source image."""

    def _roundtrip(self, protocol, send):
        kb, fw = _keyboard(protocol)
        kb.prepare_for_mru_send()
        image = _image("small", 3)
        ov = {KeyCode.KC_D.value: OverlayData(kb.device_settings, image)}
        send(kb, ov)
        kb.send_overlay_mapping({KeyCode.KC_D.value - KeyCode.KC_A.value: KeyCode.KC_D.value - KeyCode.KC_A.value})
        got = fw.sim.get_display_image(KeyCode.KC_D.value, Modifier.NO_MOD)
        np.testing.assert_array_equal(got, image)

    def test_plain(self):
        self._roundtrip(21, lambda kb, ov: kb.send_overlay_for_keycode(KeyCode.KC_D.value, Modifier.NO_MOD, ov))

    def test_plain_with_the_pre_v11_header(self):
        self._roundtrip(10, lambda kb, ov: kb.send_overlay_for_keycode(KeyCode.KC_D.value, Modifier.NO_MOD, ov))

    def test_rle(self):
        self._roundtrip(21, lambda kb, ov: kb.send_overlay_for_keycode_compressed(KeyCode.KC_D.value, Modifier.NO_MOD, ov))

    def test_roi(self):
        self._roundtrip(21, lambda kb, ov: kb.send_overlay_roi_for_keycode(KeyCode.KC_D.value, Modifier.NO_MOD, ov, False))

    def test_rle_roi(self):
        self._roundtrip(21, lambda kb, ov: kb.send_overlay_roi_for_keycode(KeyCode.KC_D.value, Modifier.NO_MOD, ov, True))

    def test_prc(self):
        kb, fw = _keyboard(19)
        images = {KeyCode.KC_A.value: _image("small", 1), KeyCode.KC_B.value: _image("corner")}
        _send(kb, images)
        self.assertTrue(fw.prc_records)
        for kc, image in images.items():
            np.testing.assert_array_equal(fw.sim.get_display_image(kc, Modifier.NO_MOD), image)

    def test_a_whole_switch_at_every_generation(self):
        images = {KeyCode.KC_A.value: _image("noise", 1), KeyCode.KC_B.value: _image("small", 2),
                  KeyCode.KC_C.value: _image("stripe"), KeyCode.KC_E.value: _image("corner")}
        for protocol in (2, 10, 12, 18, 19, 20, 21):
            with self.subTest(protocol=protocol):
                kb, fw = _keyboard(protocol)
                _send(kb, images)
                self.assertEqual(fw.refused, [])
                self.assertTrue(fw.overlays_enabled)
                for kc, image in images.items():
                    np.testing.assert_array_equal(
                        fw.sim.get_display_image(kc, Modifier.NO_MOD), image)


class SwitchTrafficTest(unittest.TestCase):
    """What a switch costs on the wire, per generation."""

    def test_a_v21_warm_switch_is_its_mapping_reports_alone(self):
        kb, fw = _keyboard(21)
        cache = OverlayMRUCache(600)
        images = {KeyCode.KC_A.value: _image("small", 1), KeyCode.KC_B.value: _image("small", 2)}
        _send(kb, images, cache)
        before = (fw.image_reports, fw.control_reports, fw.mapping_reports)
        _send(kb, images, cache)
        self.assertEqual(fw.image_reports, before[0])
        self.assertEqual(fw.control_reports, before[1])       # prepare + enable rode on cmd 33
        self.assertEqual(fw.mapping_reports, before[2] + 1)
        self.assertTrue(fw.overlays_enabled)

    def test_before_v21_prepare_and_enable_are_separate_reports(self):
        kb, fw = _keyboard(20)
        _send(kb, {KeyCode.KC_A.value: _image("small", 1)})
        self.assertEqual(fw.control_reports, 2)

    def test_mirror_keeps_an_unmapped_upload_off_the_keycaps(self):
        kb, fw = _keyboard(21)
        kb.prepare_for_mru_send()                        # sets MIRROR_OVERLAYS
        image = _image("small", 4)
        kb.send_overlay_for_keycode_compressed(
            KeyCode.KC_F.value, Modifier.NO_MOD, {KeyCode.KC_F.value: OverlayData(kb.device_settings, image)})
        self.assertIsNone(fw.sim.get_display_image(KeyCode.KC_F.value, Modifier.NO_MOD))


class IconFillTest(unittest.TestCase):

    def _icon_image(self, fw):
        frames = fw.icon_frames()
        self.assertTrue(frames, "the shipped icon library is missing")
        bits = np.unpackbits(np.frombuffer(frames[0], dtype=np.uint8))[:40 * 72]
        return bits.reshape(40, 72).astype(bool)

    def _firmware_with_icons(self, protocol):
        from polyhost.services import icon_library
        from polyhost.services.fontpack_bundle import res_dir
        version, _ = icon_library.parse((res_dir() / "icons.plyi").read_bytes())
        return {icon_library.BUNDLE_ID: version}

    def test_a_v20_keyboard_with_the_library_draws_the_icon_itself(self):
        kb, fw = _keyboard(20, bundle_versions=self._firmware_with_icons(20))
        image = self._icon_image(fw)
        _send(kb, {KeyCode.KC_A.value: image})
        self.assertEqual(fw.fill_reports, 1)
        self.assertEqual(fw.image_reports, 0)
        np.testing.assert_array_equal(fw.sim.get_display_image(KeyCode.KC_A.value, Modifier.NO_MOD), image)

    def test_a_v19_keyboard_gets_the_bitmap(self):
        kb, fw = _keyboard(19, bundle_versions=self._firmware_with_icons(19))
        image = self._icon_image(fw)
        _send(kb, {KeyCode.KC_A.value: image})
        self.assertEqual(fw.fill_reports, 0)
        self.assertGreater(fw.image_reports, 0)


class FirmwareQuirkTest(unittest.TestCase):
    """The emulator copies the firmware's behaviour, quirks included. These pin
    the two that matter to anyone reading a keycap the emulator produced."""

    def test_an_roi_upload_into_a_used_slot_keeps_the_old_pixels_outside_it(self):
        # fill_roi_overlay_buffer writes only its rectangle, and nothing clears
        # the slot first. The host therefore keeps ROI off a reused slot (see
        # ReusedSlotTest); this pins the firmware behaviour that makes it necessary.
        kb, fw = _keyboard(18)
        kb.prepare_for_mru_send()
        kc = KeyCode.KC_B.value
        noise, small = _image("noise", 7), _image("small", 8)
        kb.send_overlay_for_keycode_compressed(kc, Modifier.NO_MOD, {kc: OverlayData(kb.device_settings, noise)})
        kb.send_overlay_roi_for_keycode(kc, Modifier.NO_MOD, {kc: OverlayData(kb.device_settings, small)}, False)
        kb.send_overlay_mapping({kc - KeyCode.KC_A.value: kc - KeyCode.KC_A.value})
        shown = fw.sim.get_display_image(kc, Modifier.NO_MOD)
        self.assertGreater(int((shown & ~small).sum()), 0)

    def test_prc_clears_the_slot_so_a_v19_keyboard_does_not(self):
        kb, fw = _keyboard(19)
        cache = OverlayMRUCache(1)
        _send(kb, {KeyCode.KC_A.value: _image("noise", 7)}, cache, "@first")
        small = _image("small", 8)
        _send(kb, {KeyCode.KC_B.value: small}, cache, "@second")
        np.testing.assert_array_equal(
            fw.sim.get_display_image(KeyCode.KC_B.value, Modifier.NO_MOD), small)

    def _stored_after_y_upload(self, **kw):
        y, z = KeyCode.KC_Y.value, KeyCode.KC_Z.value
        kb, fw = _keyboard(21, letter_map={y: z, z: y}, **kw)
        kb.prepare_for_mru_send()                        # sets MIRROR_OVERLAYS
        image = _image("small", 9)
        kb.send_overlay_for_keycode_compressed(y, Modifier.NO_MOD, {y: OverlayData(kb.device_settings, image)})
        return fw.sim.stored_slots(), y - KeyCode.KC_A.value, z - KeyCode.KC_A.value

    def test_an_mru_upload_lands_at_its_pool_address(self):
        # Under MIRROR_OVERLAYS the address names a pool slot: no letter move.
        stored, y_slot, z_slot = self._stored_after_y_upload()
        self.assertIn(y_slot, stored)
        self.assertNotIn(z_slot, stored)

    def test_a_letter_addressed_upload_still_follows_the_language(self):
        # Outside MRU mode the firmware moves a letter's image to the key that
        # types that letter, so under a Y/Z swap the Y upload lands in Z.
        y, z = KeyCode.KC_Y.value, KeyCode.KC_Z.value
        kb, fw = _keyboard(21, letter_map={y: z, z: y})
        image = _image("small", 9)
        kb.send_overlay_for_keycode_compressed(y, Modifier.NO_MOD, {y: OverlayData(kb.device_settings, image)})
        stored = fw.sim.stored_slots()
        self.assertIn(z - KeyCode.KC_A.value, stored)
        self.assertNotIn(y - KeyCode.KC_A.value, stored)

    def test_firmware_before_the_fix_moved_mru_uploads_too(self):
        stored, y_slot, z_slot = self._stored_after_y_upload(mru_letter_translate=True)
        self.assertIn(z_slot, stored)
        self.assertNotIn(y_slot, stored)

    def test_a_whole_switch_under_a_letter_swapping_layout(self):
        # Digits first, so letter images land on non-letter addresses and the
        # Y- and Z-address slots hold other keys' images (O and P here).
        y, z = KeyCode.KC_Y.value, KeyCode.KC_Z.value
        digits = [KeyCode[f"KC_{d}"].value for d in "1234567890"]
        letters = list(range(KeyCode.KC_A.value, z + 1))
        images = {kc: _image("small", kc) for kc in digits + letters}

        def wrong(**kw):
            kb, fw = _keyboard(21, letter_map={y: z, z: y}, **kw)
            _send(kb, images)
            return sorted(KeyCode(kc).name for kc, img in images.items()
                          if not np.array_equal(fw.sim.get_display_image(kc, Modifier.NO_MOD), img))

        self.assertEqual(wrong(), [])
        self.assertEqual(wrong(mru_letter_translate=True), ["KC_O", "KC_P"])


class ReusedSlotTest(unittest.TestCase):
    """An image sent into a REUSED pool slot replaces the old one completely."""

    @staticmethod
    def _busy_box(seed):
        # Too busy for one PRC record, so even v19+ takes an older encoding,
        # and smaller than the frame, so ROI is the smallest of those.
        a = np.zeros((40, 72), dtype=bool)
        a[10:30, 15:57] = np.random.default_rng(seed).random((20, 42)) > 0.5
        return a

    def test_no_old_pixels_survive_at_any_generation(self):
        for protocol in (2, 10, 18, 19, 21):
            with self.subTest(protocol=protocol):
                kb, fw = _keyboard(protocol)
                cache = OverlayMRUCache(1)
                _send(kb, {KeyCode.KC_A.value: _image("noise", 7)}, cache, "@first")
                box = self._busy_box(5)
                _send(kb, {KeyCode.KC_B.value: box}, cache, "@second")
                np.testing.assert_array_equal(
                    fw.sim.get_display_image(KeyCode.KC_B.value, Modifier.NO_MOD), box)

    def test_a_clean_slot_still_gets_the_cheaper_roi(self):
        kb, fw = _keyboard(18)
        _send(kb, {KeyCode.KC_B.value: self._busy_box(5)})
        self.assertEqual(kb.stat_chosen["roi"], 1)

    def test_a_reused_slot_gets_a_full_frame_encoding(self):
        kb, fw = _keyboard(18)
        cache = OverlayMRUCache(1)
        _send(kb, {KeyCode.KC_A.value: _image("noise", 7)}, cache, "@first")
        before = dict(kb.stat_chosen)
        _send(kb, {KeyCode.KC_B.value: self._busy_box(5)}, cache, "@second")
        self.assertEqual(kb.stat_chosen["roi"], before["roi"])
        self.assertEqual(kb.stat_chosen["rle"] + kb.stat_chosen["plain"],
                         before["rle"] + before["plain"] + 1)


class IdentityTest(unittest.TestCase):

    def test_get_id_carries_the_blocks_its_protocol_has(self):
        for protocol, version_block, generation in ((5, False, False), (6, True, False),
                                                    (16, True, True), (21, True, True)):
            with self.subTest(protocol=protocol):
                kb, fw = _keyboard(protocol, bundle_versions={0: 4})
                ok, reply = kb.hid.send_and_read_validate(bytearray([0x50, 6]))
                self.assertTrue(ok)
                self.assertEqual(bool(parse_id_version_block(reply)), version_block)
                self.assertEqual(parse_id_state_generation(reply) is not None, generation)
                self.assertTrue(kb.query_version_info()[0])
                self.assertEqual(kb.protocol_version, protocol)

    def test_the_language_list_spans_reports(self):
        langs = ["enUS", "deAT", "koKR", "frFR", "itIT", "esES"] * 6
        kb, fw = _keyboard(21, languages=langs)
        ok, _ = kb.enumerate_lang()
        self.assertTrue(ok)
        self.assertEqual(kb.get_lang_list(), langs)

    def test_layer_names(self):
        kb, fw = _keyboard(21)
        ok, names = kb.get_layer_names()
        self.assertTrue(ok)
        self.assertEqual(names, fw.layer_names)


if __name__ == "__main__":
    unittest.main()
