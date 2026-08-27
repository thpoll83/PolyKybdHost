"""Unit tests for the per-feature protocol capability model and the
version-dependent plain-overlay header encoding.

The host connects across a RANGE of firmware protocols (see
polyhost.core.decisions.decide_reconnect_apply) and gates each feature by its
minimum protocol via FEATURE_MIN_PROTOCOL. Additive features simply enable when
supported; the plain-overlay upload (the one core command whose wire format
changed at protocol 11) must instead be *encoded for the device's protocol* so
an older keyboard still receives the header it understands.
"""
import unittest
from unittest.mock import MagicMock

from polyhost.device.poly_kybd import (
    PolyKybd, protocol_supports, FEATURE_MIN_PROTOCOL, MIN_SUPPORTED_PROTOCOL,
    OVERLAY_PACKED_HEADER_MIN_PROTOCOL, GLYPH_SIZE_MIN_PROTOCOL,
    MACRO_MIN_PROTOCOL,
)
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.command_ids import HidId, Cmd, GlyphScript, GlyphSize
from polyhost.device.keys import Modifier, LEGACY_MAX_MODIFIER_VALUE
from polyhost.settings import PolySettings


class _Overlay:
    """Minimal stand-in for the object send_overlay_for_keycode consumes."""
    def __init__(self, all_bytes):
        self.all_bytes = all_bytes


class TestProtocolSupports(unittest.TestCase):
    def test_min_supported_is_the_packed_lang_list_floor(self):
        self.assertEqual(MIN_SUPPORTED_PROTOCOL, FEATURE_MIN_PROTOCOL["packed_lang_list"])

    def test_none_protocol_supports_nothing_gated(self):
        for feature in FEATURE_MIN_PROTOCOL:
            self.assertFalse(protocol_supports(None, feature))

    def test_threshold_is_inclusive(self):
        for feature, minp in FEATURE_MIN_PROTOCOL.items():
            self.assertTrue(protocol_supports(minp, feature), feature)
            self.assertFalse(protocol_supports(minp - 1, feature), feature)

    def test_high_protocol_supports_everything(self):
        highest = max(FEATURE_MIN_PROTOCOL.values())
        for feature in FEATURE_MIN_PROTOCOL:
            self.assertTrue(protocol_supports(highest, feature))


class TestCapabilities(unittest.TestCase):
    def _keeb(self, protocol):
        keeb = PolyKybd(DeviceSettings(), PolySettings())
        keeb.protocol_version = protocol
        keeb.hid = MagicMock()
        return keeb

    def test_supports_matches_table(self):
        keeb = self._keeb(9)  # glyph_script threshold
        self.assertTrue(keeb.supports("glyph_script"))
        self.assertTrue(keeb.supports("os"))          # 7 <= 9
        self.assertFalse(keeb.supports("overlay_packed_header"))  # 11 > 9

    def test_capabilities_is_cached_only_no_io(self):
        keeb = self._keeb(4)
        caps = keeb.capabilities()
        # No device query was triggered (protocol was already known).
        keeb.hid.send_and_read_validate.assert_not_called()
        self.assertEqual(set(caps), set(FEATURE_MIN_PROTOCOL))
        self.assertTrue(caps["idle_style"])      # 4 <= 4
        self.assertFalse(caps["os"])             # 7 > 4

    def test_supports_lazily_queries_when_protocol_unknown(self):
        keeb = self._keeb(None)
        # query_version_info populates protocol_version from a GET_ID reply.
        keeb.query_version_info = MagicMock(
            side_effect=lambda: setattr(keeb, "protocol_version", 11) or (True, "x"))
        self.assertTrue(keeb.supports("overlay_packed_header"))
        keeb.query_version_info.assert_called_once()


class TestOverlayHeaderEncoding(unittest.TestCase):
    """The plain-overlay header must match the DEVICE's protocol.

    Protocol 11+: [id, cmd, keycode, (segment<<4)|modifier] + 60 data = 64 bytes.
    Pre-v11:      [id, cmd, keycode, modifier, segment]      + 60 data = 65 bytes.
    """
    KEYCODE = 0x04
    MOD = Modifier.SHIFT

    def _capture(self, protocol):
        keeb = PolyKybd(DeviceSettings(), PolySettings())
        keeb.protocol_version = protocol
        keeb.hid = MagicMock()
        keeb.hid.send_multiple.return_value = (True, b"")
        # 360 non-zero bytes so no segment is skipped as empty -> all 6 sent.
        data = bytes(((i % 250) + 1) for i in range(360))
        mapping = {self.KEYCODE: _Overlay(data)}
        sent = keeb.send_overlay_for_keycode(self.KEYCODE, self.MOD, mapping)
        self.assertEqual(sent, keeb.device_settings.OVERLAY_PLAIN_DATA_REPORT_COUNT)
        return [c.args[0] for c in keeb.hid.send_multiple.call_args_list]

    def test_packed_header_at_protocol_11(self):
        reports = self._capture(OVERLAY_PACKED_HEADER_MIN_PROTOCOL)
        for msg_num, rep in enumerate(reports):
            self.assertEqual(rep[0], HidId.ID_POLYKYBD.value)
            self.assertEqual(rep[1], Cmd.SEND_OVERLAY.value)
            self.assertEqual(rep[2], self.KEYCODE)
            # One packed header byte: (segment << 4) | modifier.
            self.assertEqual(rep[3], (msg_num << 4) | self.MOD.value)
            self.assertEqual(len(rep), 64)  # 4-byte header + 60 data

    def test_separate_header_pre_protocol_11(self):
        reports = self._capture(OVERLAY_PACKED_HEADER_MIN_PROTOCOL - 1)
        for msg_num, rep in enumerate(reports):
            self.assertEqual(rep[2], self.KEYCODE)
            # Two separate header bytes: modifier, then segment index.
            self.assertEqual(rep[3], self.MOD.value)
            self.assertEqual(rep[4], msg_num)
            self.assertEqual(len(rep), 65)  # 5-byte header + 60 data (pre-v11 form)

    def test_unknown_protocol_uses_pre_v11_form(self):
        # protocol_version None (pre-protocol firmware) -> the pre-v11 header.
        reports = self._capture(None)
        self.assertEqual(reports[0][3], self.MOD.value)
        self.assertEqual(reports[0][4], 0)


if __name__ == "__main__":
    unittest.main()


class TestGuiComboModifierGate(unittest.TestCase):
    """GUI combines with the other modifiers only from protocol 12.

    Below that the firmware folds every GUI+x chord onto the bare-GUI variant and
    its flat (slot, variant) index space stops at 90*9, so the host must neither
    upload images for those variants nor send mappings that address them.
    """

    def test_feature_threshold(self):
        self.assertEqual(FEATURE_MIN_PROTOCOL["gui_combo_modifiers"], 12)
        self.assertFalse(protocol_supports(11, "gui_combo_modifiers"))
        self.assertTrue(protocol_supports(12, "gui_combo_modifiers"))

    def test_modifier_value_is_the_folded_bitmask(self):
        """The variant IS the modifier bitmask — bit0 Ctrl, 1 Shift, 2 Alt, 3 GUI."""
        self.assertEqual(Modifier.GUI_KEY.value, 0b1000)
        self.assertEqual(Modifier.GUI_SHIFT.value, 0b1010)
        self.assertEqual(Modifier.GUI_CTRL_ALT_SHIFT.value, 0b1111)
        self.assertEqual([m.value for m in Modifier], list(range(16)))

    def test_legacy_ceiling_is_the_bare_gui_variant(self):
        self.assertEqual(LEGACY_MAX_MODIFIER_VALUE, Modifier.GUI_KEY.value)


class TestGlyphSize(unittest.TestCase):
    """Keycap legend size (cmd 34, protocol v13+).

    The contrast with the glyph SCRIPT one command over is the point of these
    tests: the script range is deliberately OPEN (the firmware keeps an index it
    cannot render and falls back to the normal legend, so the host may offer faces
    a given keyboard lacks), while the size range is CLOSED — every value has to
    name a rendering tier the firmware knows, so it NACKs anything else.
    """

    def _keeb(self, protocol):
        keeb = PolyKybd(DeviceSettings(), PolySettings())
        keeb.protocol_version = protocol
        keeb.hid = MagicMock()
        return keeb

    def test_feature_threshold(self):
        self.assertEqual(FEATURE_MIN_PROTOCOL["glyph_size"], GLYPH_SIZE_MIN_PROTOCOL)
        self.assertFalse(protocol_supports(GLYPH_SIZE_MIN_PROTOCOL - 1, "glyph_size"))
        self.assertTrue(protocol_supports(GLYPH_SIZE_MIN_PROTOCOL, "glyph_size"))

    def test_old_firmware_refuses_without_touching_the_device(self):
        """The gate must fail BEFORE any I/O — an ungated command would connect
        and then NACK at runtime, which is the failure the range-connect model
        exists to prevent."""
        keeb = self._keeb(GLYPH_SIZE_MIN_PROTOCOL - 1)
        ok, msg = keeb.set_glyph_size(GlyphSize.LARGE)
        self.assertFalse(ok)
        self.assertIn("too old", msg)
        keeb.hid.send_and_read_validate.assert_not_called()
        ok, value = keeb.get_glyph_size()
        self.assertFalse(ok)
        self.assertEqual(value, 0)
        keeb.hid.send_and_read_validate.assert_not_called()

    def test_set_sends_the_enum_value_on_cmd_34(self):
        keeb = self._keeb(GLYPH_SIZE_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (True, b"P\x22.")
        ok, _ = keeb.set_glyph_size(GlyphSize.MEDIUM)
        self.assertTrue(ok)
        report = keeb.hid.send_and_read_validate.call_args.args[0]
        self.assertEqual(report[1], Cmd.GLYPH_SIZE.value)
        self.assertEqual(report[2], GlyphSize.MEDIUM.value)

    def test_get_queries_with_the_0xff_sentinel_and_reads_data3(self):
        keeb = self._keeb(GLYPH_SIZE_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (
            True, bytes([ord("P"), Cmd.GLYPH_SIZE.value, ord("."), GlyphSize.LARGE.value]))
        ok, value = keeb.get_glyph_size()
        self.assertTrue(ok)
        self.assertEqual(value, GlyphSize.LARGE.value)
        report = keeb.hid.send_and_read_validate.call_args.args[0]
        self.assertEqual(report[2], 0xFF)

    def test_a_nacked_reply_is_not_read_as_a_size(self):
        """The firmware answers 'P\x22!' for a value it does not know. Reading
        data[3] regardless would hand back whatever byte followed the NACK."""
        keeb = self._keeb(GLYPH_SIZE_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (
            True, bytes([ord("P"), Cmd.GLYPH_SIZE.value, ord("!"), 7]))
        ok, value = keeb.get_glyph_size()
        self.assertFalse(ok)
        self.assertEqual(value, 0)

    def test_command_id_and_enum_match_the_firmware(self):
        self.assertEqual(Cmd.GLYPH_SIZE.value, 34)
        # poly_glyph_size in the firmware's state.h — append-only, never reordered.
        self.assertEqual([(s.name, s.value) for s in GlyphSize],
                         [("SMALL", 0), ("MEDIUM", 1), ("LARGE", 2)])

    def test_size_is_a_closed_range_unlike_the_script(self):
        """Documented contrast, pinned so a future 'make it open like the script'
        change has to confront it: GlyphScript is open-ended by design, GlyphSize
        is not, and SMALL/STANDARD are both 0 so neither ever needs a migration."""
        self.assertEqual(GlyphSize.SMALL.value, 0)
        self.assertEqual(GlyphScript.STANDARD.value, 0)
        self.assertEqual(max(s.value for s in GlyphSize), 2)


class MacroCapabilityTest(unittest.TestCase):
    """Macros are three commands behind ONE gate (cmds 36/37/38, protocol v15+).

    All three go through the same ``supports("macros")`` check, because a host that
    could read the info header but not the bodies would render an editor over data it
    cannot fetch -- worse than a cleanly disabled tab.
    """

    def _keeb(self, protocol):
        keeb = PolyKybd(DeviceSettings(), PolySettings())
        keeb.protocol_version = protocol
        keeb.hid = MagicMock()
        return keeb

    def test_feature_threshold(self):
        self.assertEqual(FEATURE_MIN_PROTOCOL["macros"], MACRO_MIN_PROTOCOL)
        self.assertFalse(protocol_supports(MACRO_MIN_PROTOCOL - 1, "macros"))
        self.assertTrue(protocol_supports(MACRO_MIN_PROTOCOL, "macros"))

    def test_every_macro_command_refuses_without_touching_the_device(self):
        """The gate must fail BEFORE any I/O, on all three commands. Gating only the
        writer would let the editor load a list from a keyboard that cannot save it."""
        keeb = self._keeb(MACRO_MIN_PROTOCOL - 1)
        for call in (lambda: keeb.get_macro_info(),
                     lambda: keeb.read_macro_buffer(64),
                     lambda: keeb.write_macro_buffer(b"\0"),
                     lambda: keeb.get_macro_look(0),
                     lambda: keeb.set_macro_look(0, "x")):
            with self.subTest(call=call):
                ok, msg = call()
                self.assertFalse(ok)
                self.assertIn("too old", msg)
        keeb.hid.send_and_read_validate.assert_not_called()

    def test_info_decodes_the_header(self):
        keeb = self._keeb(MACRO_MIN_PROTOCOL)
        # count, label stride, capacity LE, used LE, style count
        keeb.hid.send_and_read_validate.return_value = (True, bytes(
            [ord("P"), Cmd.MACRO_INFO.value, ord("."), 16, 12, 0xDB, 0x08, 0x2A, 0x01, 3]))
        ok, info = keeb.get_macro_info()
        self.assertTrue(ok)
        self.assertEqual(info, {"count": 16, "label_len": 12,
                                "capacity": 2267, "used": 298, "styles": 3})

    def test_a_firmware_without_the_style_byte_reports_one_style(self):
        """The byte was appended after the macro commands shipped, so a reply that
        stops at `used` is a real firmware -- and it draws exactly the index style.
        Reporting 0 would make a host menu offer nothing at all."""
        keeb = self._keeb(MACRO_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (True, bytes(
            [ord("P"), Cmd.MACRO_INFO.value, ord("."), 16, 12, 0xDB, 0x08, 0x2A, 0x01]))
        ok, info = keeb.get_macro_info()
        self.assertTrue(ok)
        self.assertEqual(info["styles"], 1)

    def test_a_short_reply_is_not_read_as_a_header(self):
        """Reading past a truncated reply would hand back a capacity of whatever
        followed it -- and the editor sizes its storage bar from that number."""
        keeb = self._keeb(MACRO_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (
            True, bytes([ord("P"), Cmd.MACRO_INFO.value, ord("."), 16]))
        ok, _ = keeb.get_macro_info()
        self.assertFalse(ok)

    def test_a_nacked_reply_is_not_read_as_a_header(self):
        keeb = self._keeb(MACRO_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (True, bytes(
            [ord("P"), Cmd.MACRO_INFO.value, ord("!"), 9, 9, 9, 9, 9, 9]))
        ok, _ = keeb.get_macro_info()
        self.assertFalse(ok)

    def _look_reply(self, label=b"caf ", style=0, icon=0):
        return (True, bytes([ord("P"), Cmd.MACRO_LABEL.value, ord("."), len(label), style])
                + icon.to_bytes(4, "little") + label)

    def test_label_set_drops_what_the_face_cannot_draw(self):
        """The _Nano_ face is 0x20..0x7E. Sending a character it cannot draw would
        make the keycap show less than the user typed, which reads as a bug."""
        keeb = self._keeb(MACRO_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = self._look_reply()
        ok, _ = keeb.set_macro_look(0, "caf\u00e9 \u2764")
        self.assertTrue(ok)
        report = keeb.hid.send_and_read_validate.call_args.args[0]
        self.assertEqual(bytes(report[keeb.MACRO_LOOK_HEADER:]), b"caf ")
        self.assertEqual(report[3], 4)   # the length must match what was sent

    def test_the_look_travels_as_one_write(self):
        """Caption, style and icon share a single exchange, so a keycap can never be
        left composing a caption with a style from a different moment."""
        keeb = self._keeb(MACRO_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = self._look_reply(
            b"mail", style=1, icon=0x1F4E7)
        ok, look = keeb.set_macro_look(0, "mail", 1, 0x1F4E7)
        self.assertTrue(ok)
        self.assertEqual(look, {"label": "mail", "style": 1, "icon": 0x1F4E7})
        report = keeb.hid.send_and_read_validate.call_args.args[0]
        self.assertEqual(report[4], 1)
        self.assertEqual(int.from_bytes(bytes(report[5:9]), "little"), 0x1F4E7)

    def test_an_icon_past_the_bmp_survives_the_round_trip(self):
        """The interesting glyphs are emoji at 0x1F300+, so a 16-bit field would have
        silently truncated exactly the codepoints this feature exists for."""
        keeb = self._keeb(MACRO_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = self._look_reply(
            b"x", style=1, icon=0x1F680)
        ok, look = keeb.set_macro_look(0, "x", 1, 0x1F680)
        self.assertTrue(ok)
        self.assertEqual(look["icon"], 0x1F680)

    def test_body_read_walks_the_buffer_in_windows(self):
        keeb = self._keeb(MACRO_MIN_PROTOCOL)
        chunk = keeb.MACRO_BODY_CHUNK

        def reply(cmd, *_a, **_k):
            want = cmd[5]
            return True, bytes([ord("P"), Cmd.MACRO_BODY.value, ord("."), want, 0, 0]) + bytes(want)

        keeb.hid.send_and_read_validate.side_effect = reply
        ok, data = keeb.read_macro_buffer(chunk + 5)
        self.assertTrue(ok)
        self.assertEqual(len(data), chunk + 5)
        # Two reports: a full window then the remainder, with the offset advancing.
        offsets = [c.args[0][3] | (c.args[0][4] << 8)
                   for c in keeb.hid.send_and_read_validate.call_args_list]
        self.assertEqual(offsets, [0, chunk])

    def test_a_read_that_returns_nothing_stops_rather_than_spinning(self):
        """A zero-length window would leave the offset where it was, so a naive loop
        would re-request it forever."""
        keeb = self._keeb(MACRO_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (
            True, bytes([ord("P"), Cmd.MACRO_BODY.value, ord("."), 0, 0, 0]))
        ok, msg = keeb.read_macro_buffer(128)
        self.assertFalse(ok)
        self.assertIn("nothing", msg)

    def test_a_write_raises_an_in_progress_marker_first(self):
        """An interrupted upload must leave the buffer UNPLAYABLE.

        The firmware refuses to play a buffer whose last byte is not NUL. That guard
        is inert on its own -- join_buffer() zero-fills to capacity, so the byte reads
        0 throughout and the guard could never fire, leaving a half-written buffer
        playable as a splice of new text and whatever preceded it. So the host raises
        a non-zero marker at the end BEFORE streaming, and the final window carries
        the real trailing NUL that clears it.
        """
        keeb = self._keeb(MACRO_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (
            True, bytes([ord("P"), Cmd.MACRO_BODY.value, ord(".")]))
        data = bytes(range(1, 200)) + b"\0"
        ok, _ = keeb.write_macro_buffer(data)
        self.assertTrue(ok)

        sent = [c.args[0] for c in keeb.hid.send_and_read_validate.call_args_list]
        last = len(data) - 1

        first = sent[0]
        self.assertEqual(first[3] | (first[4] << 8), last, "marker not at the end")
        self.assertEqual(first[5], 1)
        self.assertNotEqual(first[6], 0, "the marker must be non-zero to arm the guard")

        # ...and the streaming that follows starts at 0 and ends by writing the real
        # trailing NUL over the marker.
        self.assertEqual(sent[1][3] | (sent[1][4] << 8), 0)
        final = sent[-1]
        off, n = final[3] | (final[4] << 8), final[5]
        self.assertEqual(off + n, len(data), "the last window must reach the end")
        self.assertEqual(final[6:6 + n][-1], 0, "the last byte written must be NUL")

    def test_a_refused_marker_aborts_before_any_data_is_written(self):
        """Failing closed matters more than failing late: if the guard cannot be armed
        we must not go on to overwrite macros that are currently intact."""
        keeb = self._keeb(MACRO_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (True, b"P\x25!")
        ok, msg = keeb.write_macro_buffer(bytes(100))
        self.assertFalse(ok)
        self.assertIn("mark", msg)
        self.assertEqual(keeb.hid.send_and_read_validate.call_count, 1)

    def test_command_ids_match_the_firmware(self):
        # These moved once already: cmd 35 was taken by GET_LAYER_NAMES on a branch
        # that landed first, so the macros shifted up one and the protocol floor went
        # v14 -> v15. That is exactly the collision this assertion exists to catch --
        # a host talking to the wrong command reads a plausible reply from a real
        # feature rather than failing, so nothing else here would have noticed.
        self.assertEqual(Cmd.GET_LAYER_NAMES.value, 35)
        self.assertEqual(Cmd.MACRO_INFO.value, 36)
        self.assertEqual(Cmd.MACRO_BODY.value, 37)
        self.assertEqual(Cmd.MACRO_LABEL.value, 38)
