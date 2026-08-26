"""Tests for GET_LAYER_NAMES (cmd 35, protocol v14+).

The keyboard reports what its host-remappable layers are called so the layout
editor stops labelling tabs from res/layer_names.yaml — a build-time artifact
generated from the firmware's layers.h, which silently went stale for two renames
of its source path and described an enum the firmware no longer had.

decode_layer_names is pure, so the wire contract is pinned here without a device:
the total byte, the count, the NUL terminators, the firmware's zero-filled tail,
and the "still incomplete" signal a multi-report read terminates on.
"""
import unittest

from polyhost.device.command_ids import Cmd
from polyhost.device.poly_kybd import (
    decode_layer_names, FEATURE_MIN_PROTOCOL, LAYER_NAMES_MIN_PROTOCOL,
    LAYER_NAME_MAX, LAYER_NAMES_HEADER,
)

from tests.device.poly_kybd_cmd_test import make_keeb, POLY
from tests.device.fake_hid import ack, nack, pad

# What the firmware's layer_names.c names today.
NAMES = ["Qwerty", "Stag!", "ColemkDH", "Neo", "Workman", "Fn", "Numpad", "Utility"]
REPORT_PAYLOAD = 64 - 3   # 61 bytes after the "P<cmd>." header


def payload(names) -> bytes:
    """Encode exactly as the firmware does: total, count, NUL-terminated names."""
    body = b"".join(n.encode("ascii") + b"\x00" for n in names)
    return bytes([LAYER_NAMES_HEADER + len(body), len(names)]) + body


class TestWireContract(unittest.TestCase):
    def test_command_id_matches_firmware(self):
        # Firmware hid_com.c dispatches this as case 35.
        self.assertEqual(Cmd.GET_LAYER_NAMES.value, 35)

    def test_feature_gate_registered_at_v14(self):
        self.assertEqual(FEATURE_MIN_PROTOCOL["layer_names"], 14)
        self.assertEqual(LAYER_NAMES_MIN_PROTOCOL, 14)

    def test_total_byte_describes_the_whole_payload(self):
        p = payload(NAMES)
        self.assertEqual(p[0], len(p))

    def test_todays_reply_fits_one_report(self):
        # 54 bytes into 61 — the whole point of carrying a total instead of
        # padding every record out to a fixed width.
        self.assertLessEqual(len(payload(NAMES)), REPORT_PAYLOAD)

    def test_names_fit_the_budget(self):
        for name in NAMES:
            self.assertLessEqual(len(name), LAYER_NAME_MAX, name)

    def test_total_stays_addressable_by_one_byte(self):
        # Mirrors the firmware's _Static_assert on LAYER_NAMES_PAYLOAD_MAX.
        worst = LAYER_NAMES_HEADER + len(NAMES) * (LAYER_NAME_MAX + 1)
        self.assertLessEqual(worst, 255)


class TestDecodeLayerNames(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(decode_layer_names(payload(NAMES)), NAMES)

    def test_zero_fill_past_the_total_is_never_examined(self):
        # The firmware memsets the report before filling it, so the tail of the
        # last report is NULs. The total says where the payload ends, so they
        # cannot be mistaken for name separators.
        self.assertEqual(decode_layer_names(pad(payload(NAMES))), NAMES)

    def test_an_unnamed_layer_survives_the_round_trip(self):
        # THE case that decided this encoding. poly_layer_name_wire() returns NULL
        # for a layer it does not name, which the firmware emits as a bare
        # terminator. Without the total, that byte is indistinguishable from the
        # report's zero fill and the list silently truncates.
        names = ["Qwerty", "Stag!", "", "Neo"]
        self.assertEqual(decode_layer_names(pad(payload(names))), names)

    def test_incomplete_payload_returns_none(self):
        full = payload(NAMES)
        for cut in range(1, len(full)):
            self.assertIsNone(decode_layer_names(full[:cut]),
                              f"{cut} bytes should read as incomplete")

    def test_empty_payload_returns_none(self):
        self.assertIsNone(decode_layer_names(b""))

    def test_implausible_total_is_refused(self):
        # An all-zero or garbage read must not decode as "0 layers, success".
        for total in (0, 1, 2):
            self.assertIsNone(decode_layer_names(bytes([total, 0]) + b"\x00" * 40))

    def test_extra_trailing_bytes_are_ignored(self):
        # The total is authoritative: a longer buffer must not grow the list.
        self.assertEqual(decode_layer_names(payload(NAMES) + b"Extra\x00"), NAMES)

    def test_count_larger_than_the_body_is_incomplete(self):
        # PADDED, which is the whole point: if the decoder slices past the total
        # it reads the report's zero fill, and those NULs supply the missing
        # fields as empty names — the exact forgery the total byte prevents.
        p = bytearray(payload(NAMES))
        p[1] = len(NAMES) + 3           # claims more names than the body carries
        self.assertIsNone(decode_layer_names(pad(bytes(p))))

    def test_a_full_width_name_needs_no_special_case(self):
        self.assertEqual(decode_layer_names(payload(["ColemkDH"])), ["ColemkDH"])

    def test_non_ascii_does_not_raise(self):
        self.assertEqual(decode_layer_names(bytes([4, 1]) + b"\xff\x00"), ["�"])


class TestGetLayerNames(unittest.TestCase):
    def test_reads_a_single_report_reply(self):
        keeb, device = make_keeb(replies=[ack(35, payload(NAMES))])
        keeb.protocol_version = 14
        ok, names = keeb.get_layer_names()
        self.assertTrue(ok)
        self.assertEqual(names, NAMES)
        self.assertEqual(device.last_payload()[:2], bytes([POLY, 35]))
        self.assertFalse(keeb.hid.lock.locked())

    def test_reassembles_a_reply_that_spans_two_reports(self):
        # Today's 8 layers fit one report, so force the multi-report path with a
        # longer set. Chunk it the way the firmware does: every report but the
        # last is FULL — a short non-final report is something it cannot emit.
        long_names = NAMES + ["Settings", "Language", "Intl", "Emoji"]
        body = payload(long_names)
        self.assertGreater(len(body), REPORT_PAYLOAD, "fixture no longer spans reports")
        reports = [ack(35, body[off:off + REPORT_PAYLOAD])
                   for off in range(0, len(body), REPORT_PAYLOAD)]
        self.assertEqual(len(reports), 2)
        keeb, _ = make_keeb(replies=reports)
        keeb.protocol_version = 14
        ok, names = keeb.get_layer_names()
        self.assertTrue(ok)
        self.assertEqual(names, long_names)

    def test_a_lost_continuation_fails_rather_than_returning_partial_names(self):
        long_names = NAMES + ["Settings", "Language", "Intl", "Emoji"]
        body = payload(long_names)
        keeb, _ = make_keeb(replies=[ack(35, body[:REPORT_PAYLOAD])])   # second report never arrives
        keeb.protocol_version = 14
        ok, names = keeb.get_layer_names()
        self.assertFalse(ok)
        self.assertEqual(names, [])

    def test_nack_is_a_failure(self):
        keeb, _ = make_keeb(replies=[nack(35)])
        keeb.protocol_version = 14
        ok, names = keeb.get_layer_names()
        self.assertFalse(ok)
        self.assertEqual(names, [])

    def test_old_firmware_is_gated_off_without_touching_the_device(self):
        keeb, device = make_keeb(replies=[ack(35, payload(NAMES))])
        keeb.protocol_version = LAYER_NAMES_MIN_PROTOCOL - 1
        ok, names = keeb.get_layer_names()
        self.assertFalse(ok)
        self.assertEqual(names, [])
        self.assertEqual(device.writes, [], "must not send a command it knows is unsupported")


if __name__ == "__main__":
    unittest.main()
