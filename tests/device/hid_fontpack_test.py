"""Tests for polyhost.device.hid_fontpack.

All tests use a lightweight mock HID object; no real hardware is required.
Mirrors hid_fw_up_test.py — the font-pack flash reuses the firmware-update
BEGIN/CHUNK/COMMIT protocol, so the flow tests are structurally identical
(poll, NACK-retry, resume-rewind, cancel, progress); the differences are the
command bytes (0x50–0x53), the "PlyF" pack fixture, and that COMMIT is terminal
(no apply / reboot).
"""
import binascii
import os
import struct
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from polyhost.device.hid_fontpack import (
    parse_fontpack_header,
    validate_fontpack,
    get_fontpack_status,
    flash_fontpack,
    parse_id_version_block,
    decide_stale_bundles,
    HID_POLYKYBD,
    CMD_FONTPACK_BEGIN,
    CMD_FONTPACK_CHUNK,
    CMD_FONTPACK_COMMIT,
    CMD_FONTPACK_STATUS,
    FONTPACK_CHUNK_SIZE,
    FONTPACK_MAX_SIZE,
    FONTPACK_ABI_VERSION,
    _HEADER_SIZE,
)

ACK  = ord('.')
NACK = ord('!')
POLL = ord('~')


# ---------------------------------------------------------------------------
# Pack fixture helpers
# ---------------------------------------------------------------------------

def _make_pack(body: bytes = b'\xAB' * 248, content_version: int = 7,
               font_count: int = 3, abi: int = FONTPACK_ABI_VERSION) -> bytes:
    """Build a structurally-valid 'PlyF' pack. Default body 248 B -> 280 B total
    = exactly 5 chunks of 56 B (no padding on the last chunk)."""
    total = _HEADER_SIZE + len(body)
    crc = binascii.crc32(body) & 0xFFFFFFFF
    hdr = struct.pack("<4sHHIIIIII", b"PlyF", abi, 0, content_version,
                      font_count, _HEADER_SIZE, total, crc, 0)
    return hdr + body


def _chunks(pack: bytes) -> int:
    return (len(pack) + FONTPACK_CHUNK_SIZE - 1) // FONTPACK_CHUNK_SIZE


def _write_bin(data: bytes) -> str:
    fd, path = tempfile.mkstemp(suffix='.plyf')
    os.write(fd, data)
    os.close(fd)
    return path


# ---------------------------------------------------------------------------
# HID mock helpers
# ---------------------------------------------------------------------------

def _ack_reply(cmd: int, extra: bytes = b'') -> bytearray:
    buf = bytearray(64)
    buf[0] = HID_POLYKYBD
    buf[1] = cmd
    buf[2] = ACK
    buf[3:3 + len(extra)] = extra
    return buf


def _nack_reply(cmd: int) -> bytearray:
    buf = bytearray(64)
    buf[0] = HID_POLYKYBD
    buf[1] = cmd
    buf[2] = NACK
    return buf


def _poll_reply(cmd: int) -> bytearray:
    buf = bytearray(64)
    buf[0] = HID_POLYKYBD
    buf[1] = cmd
    buf[2] = POLL
    return buf


def _status_reply(present: int, abi: int, content_version: int, font_count: int) -> bytearray:
    buf = _ack_reply(CMD_FONTPACK_STATUS)
    buf[3] = present
    buf[4] = abi
    struct.pack_into('<H', buf, 5, content_version)
    buf[7] = font_count
    return buf


def _make_hid(side_effects, reconnect=False):
    hid = MagicMock()
    hid.send_and_read.side_effect = side_effects
    hid.wait_for_reconnect.return_value = reconnect
    return hid


def _flash_hid(pack: bytes):
    """Mock HID that ACKs the exact BEGIN + N*CHUNK + COMMIT sequence."""
    n = _chunks(pack)
    return _make_hid(
        [(True, _ack_reply(CMD_FONTPACK_BEGIN))] +
        [(True, _ack_reply(CMD_FONTPACK_CHUNK))] * n +
        [(True, _ack_reply(CMD_FONTPACK_COMMIT))]
    )


# ---------------------------------------------------------------------------
# parse_fontpack_header / validate_fontpack
# ---------------------------------------------------------------------------

class TestValidateFontpack(unittest.TestCase):

    def test_valid_pack_parses_all_fields(self):
        ok, info = parse_fontpack_header(_make_pack(content_version=42, font_count=9))
        self.assertTrue(ok)
        self.assertEqual(info['content_version'], 42)
        self.assertEqual(info['font_count'], 9)
        self.assertEqual(info['abi_version'], FONTPACK_ABI_VERSION)

    def test_valid_pack_validates(self):
        ok, msg = validate_fontpack(_make_pack())
        self.assertTrue(ok)
        self.assertEqual(msg, '')

    def test_empty_rejected(self):
        ok, msg = validate_fontpack(b'')
        self.assertFalse(ok)
        self.assertIn('empty', msg.lower())

    def test_too_large_rejected(self):
        ok, msg = validate_fontpack(b'\x00' * (FONTPACK_MAX_SIZE + 1))
        self.assertFalse(ok)
        self.assertIn('large', msg.lower())

    def test_bad_magic_rejected(self):
        pack = bytearray(_make_pack())
        pack[0:4] = b'XXXX'
        ok, msg = validate_fontpack(bytes(pack))
        self.assertFalse(ok)
        self.assertIn('magic', msg.lower())

    def test_abi_mismatch_rejected(self):
        ok, msg = validate_fontpack(_make_pack(abi=FONTPACK_ABI_VERSION + 1))
        self.assertFalse(ok)
        self.assertIn('abi', msg.lower())

    def test_size_mismatch_rejected(self):
        ok, msg = validate_fontpack(_make_pack() + b'\xff')
        self.assertFalse(ok)
        self.assertIn('total_size', msg.lower())

    def test_corrupt_body_crc_rejected(self):
        pack = bytearray(_make_pack())
        pack[-1] ^= 0xFF
        ok, msg = validate_fontpack(bytes(pack))
        self.assertFalse(ok)
        self.assertIn('crc', msg.lower())

    def test_truncated_header_rejected(self):
        ok, msg = validate_fontpack(_make_pack()[:10])
        self.assertFalse(ok)


# ---------------------------------------------------------------------------
# get_fontpack_status
# ---------------------------------------------------------------------------

class TestGetFontpackStatus(unittest.TestCase):

    def test_present_pack_parsed(self):
        hid = _make_hid([(True, _status_reply(1, 1, 42, 9))])
        ok, info = get_fontpack_status(hid)
        self.assertTrue(ok)
        self.assertEqual(info, {"present": True, "abi": 1, "content_version": 42, "font_count": 9})

    def test_absent_pack_present_false(self):
        hid = _make_hid([(True, _status_reply(0, 1, 0, 0))])
        ok, info = get_fontpack_status(hid)
        self.assertTrue(ok)
        self.assertFalse(info['present'])

    def test_request_packet_format(self):
        hid = _make_hid([(True, _status_reply(1, 1, 1, 1))])
        get_fontpack_status(hid)
        pkt = hid.send_and_read.call_args[0][0]
        self.assertEqual(pkt[0], HID_POLYKYBD)
        self.assertEqual(pkt[1], CMD_FONTPACK_STATUS)

    def test_hid_failure_returns_false(self):
        hid = _make_hid([(False, bytearray(64))])
        ok, info = get_fontpack_status(hid)
        self.assertFalse(ok)
        self.assertEqual(info, {})

    def test_nack_returns_false(self):
        hid = _make_hid([(True, _nack_reply(CMD_FONTPACK_STATUS))])
        ok, _ = get_fontpack_status(hid)
        self.assertFalse(ok)

    def test_short_reply_returns_false(self):
        hid = _make_hid([(True, bytearray(5))])
        ok, _ = get_fontpack_status(hid)
        self.assertFalse(ok)


# ---------------------------------------------------------------------------
# flash_fontpack -- validation
# ---------------------------------------------------------------------------

class TestFlashFontpackValidation(unittest.TestCase):

    def test_empty_file_rejected_before_hid(self):
        path = _write_bin(b'')
        hid = MagicMock()
        try:
            ok, msg = flash_fontpack(hid, path)
            self.assertFalse(ok)
            hid.send_and_read.assert_not_called()
        finally:
            os.unlink(path)

    def test_garbage_rejected_before_hid(self):
        path = _write_bin(b'\xAB' * 300)
        hid = MagicMock()
        try:
            ok, msg = flash_fontpack(hid, path)
            self.assertFalse(ok)
            self.assertIn('magic', msg.lower())
            hid.send_and_read.assert_not_called()
        finally:
            os.unlink(path)

    def test_valid_pack_proceeds_to_hid(self):
        path = _write_bin(_make_pack())
        try:
            hid = _make_hid([(False, bytearray(64))], reconnect=False)
            ok, msg = flash_fontpack(hid, path)
            self.assertFalse(ok)        # BEGIN dropout, no reconnect
            self.assertIn('BEGIN', msg)
            hid.send_and_read.assert_called()
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_fontpack -- BEGIN
# ---------------------------------------------------------------------------

class TestFlashFontpackBegin(unittest.TestCase):

    def test_begin_packet_byte_layout(self):
        pack = _make_pack()
        path = _write_bin(pack)
        try:
            expected_crc = binascii.crc32(pack) & 0xFFFFFFFF
            hid = _flash_hid(pack)
            flash_fontpack(hid, path)
            begin = hid.send_and_read.call_args_list[0][0][0]
            self.assertEqual(begin[0], HID_POLYKYBD)
            self.assertEqual(begin[1], CMD_FONTPACK_BEGIN)
            size_field = struct.unpack_from('<I', bytes(begin), 2)[0]
            crc_field  = struct.unpack_from('<I', bytes(begin), 6)[0]
            self.assertEqual(size_field, len(pack))
            self.assertEqual(crc_field, expected_crc)   # whole-pack transport CRC
        finally:
            os.unlink(path)

    def test_begin_poll_repolls_until_ready(self):
        pack = _make_pack()
        path = _write_bin(pack)
        n = _chunks(pack)
        try:
            hid = _make_hid(
                [(True, _poll_reply(CMD_FONTPACK_BEGIN))] * 2 +
                [(True, _ack_reply(CMD_FONTPACK_BEGIN))] +
                [(True, _ack_reply(CMD_FONTPACK_CHUNK))] * n +
                [(True, _ack_reply(CMD_FONTPACK_COMMIT))]
            )
            with patch('polyhost.device.hid_fontpack.time.sleep'):
                ok, msg = flash_fontpack(hid, path)
            self.assertTrue(ok, msg)
            for i in range(3):
                self.assertEqual(hid.send_and_read.call_args_list[i][0][0][1], CMD_FONTPACK_BEGIN)
        finally:
            os.unlink(path)

    def test_begin_usb_dropout_triggers_reconnect(self):
        pack = _make_pack()
        path = _write_bin(pack)
        n = _chunks(pack)
        try:
            hid = _make_hid(
                [(False, bytearray(64))] +
                [(True, _ack_reply(CMD_FONTPACK_BEGIN))] +
                [(True, _ack_reply(CMD_FONTPACK_CHUNK))] * n +
                [(True, _ack_reply(CMD_FONTPACK_COMMIT))],
                reconnect=True,
            )
            ok, msg = flash_fontpack(hid, path)
            self.assertTrue(ok, msg)
            hid.wait_for_reconnect.assert_called_once_with(timeout_s=30)
        finally:
            os.unlink(path)

    def test_begin_nack_returns_false(self):
        path = _write_bin(_make_pack())
        try:
            hid = _make_hid([(True, _nack_reply(CMD_FONTPACK_BEGIN))])
            ok, msg = flash_fontpack(hid, path)
            self.assertFalse(ok)
            self.assertIn('BEGIN', msg)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_fontpack -- CHUNK
# ---------------------------------------------------------------------------

class TestFlashFontpackChunks(unittest.TestCase):

    def test_correct_chunk_count_and_offsets(self):
        pack = _make_pack()          # 280 B = 5 chunks
        path = _write_bin(pack)
        try:
            hid = _flash_hid(pack)
            ok, _ = flash_fontpack(hid, path)
            self.assertTrue(ok)
            self.assertEqual(hid.send_and_read.call_count, 7)   # 1 BEGIN + 5 + 1 COMMIT
            for i in range(5):
                pkt = hid.send_and_read.call_args_list[1 + i][0][0]
                self.assertEqual(pkt[1], CMD_FONTPACK_CHUNK)
                self.assertEqual(struct.unpack_from('<I', bytes(pkt), 2)[0], i * FONTPACK_CHUNK_SIZE)
        finally:
            os.unlink(path)

    def test_partial_last_chunk_padded_with_ff(self):
        pack = _make_pack(body=b'\xAB' * 249)   # 281 B -> 6 chunks; last has 1 real byte
        path = _write_bin(pack)
        try:
            hid = _flash_hid(pack)
            flash_fontpack(hid, path)
            last = hid.send_and_read.call_args_list[6][0][0]
            self.assertEqual(bytes(last[6:7]), pack[280:281])
            self.assertEqual(bytes(last[7:6 + FONTPACK_CHUNK_SIZE]), b'\xff' * 55)
        finally:
            os.unlink(path)

    def test_chunk_nack_with_resume_rewinds(self):
        pack = _make_pack()          # 5 chunks
        path = _write_bin(pack)
        n = _chunks(pack)
        sent = []

        def nack_resume(resume):
            buf = _nack_reply(CMD_FONTPACK_CHUNK)
            struct.pack_into('<I', buf, 3, resume)
            return buf

        replies = iter(
            [(True, _ack_reply(CMD_FONTPACK_BEGIN))] +
            [(True, _ack_reply(CMD_FONTPACK_CHUNK))] * 3 +
            [(True, nack_resume(1 * FONTPACK_CHUNK_SIZE))] +
            [(True, _ack_reply(CMD_FONTPACK_CHUNK))] * (n - 1) +
            [(True, _ack_reply(CMD_FONTPACK_COMMIT))]
        )

        def side_effect(pkt, timeout):
            if pkt[1] == CMD_FONTPACK_CHUNK:
                sent.append(struct.unpack_from('<I', pkt, 2)[0])
            return next(replies)

        try:
            with patch('polyhost.device.hid_fontpack.time.sleep'):
                hid = MagicMock()
                hid.send_and_read.side_effect = side_effect
                ok, _ = flash_fontpack(hid, path)
            self.assertTrue(ok)
            self.assertEqual(sent, [0, 56, 112, 168, 56, 112, 168, 224])
        finally:
            os.unlink(path)

    def test_chunk_fails_after_attempts_with_cleanup(self):
        path = _write_bin(_make_pack())
        try:
            with patch('polyhost.device.hid_fontpack.time.sleep'):
                hid = _make_hid(
                    [(True, _ack_reply(CMD_FONTPACK_BEGIN))] +
                    [(True, _nack_reply(CMD_FONTPACK_CHUNK))] * 8 +
                    [(True, _nack_reply(CMD_FONTPACK_COMMIT))]   # cleanup commit
                )
                ok, msg = flash_fontpack(hid, path)
            self.assertFalse(ok)
            self.assertIn('CHUNK', msg)
            self.assertEqual(hid.send_and_read.call_count, 10)  # 1 + 8 + cleanup
            self.assertEqual(hid.send_and_read.call_args_list[-1][0][0][1], CMD_FONTPACK_COMMIT)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_fontpack -- COMMIT (terminal; no apply)
# ---------------------------------------------------------------------------

class TestFlashFontpackCommit(unittest.TestCase):

    def test_commit_packet_format(self):
        pack = _make_pack()
        path = _write_bin(pack)
        try:
            hid = _flash_hid(pack)
            flash_fontpack(hid, path)
            commit = hid.send_and_read.call_args_list[-1][0][0]
            self.assertEqual(commit[0], HID_POLYKYBD)
            self.assertEqual(commit[1], CMD_FONTPACK_COMMIT)
        finally:
            os.unlink(path)

    def test_commit_reads_content_version_from_reply(self):
        pack = _make_pack(content_version=99)
        path = _write_bin(pack)
        n = _chunks(pack)
        try:
            commit_reply = _ack_reply(CMD_FONTPACK_COMMIT, struct.pack('<H', 99))
            hid = _make_hid(
                [(True, _ack_reply(CMD_FONTPACK_BEGIN))] +
                [(True, _ack_reply(CMD_FONTPACK_CHUNK))] * n +
                [(True, commit_reply)]
            )
            ok, msg = flash_fontpack(hid, path)
            self.assertTrue(ok)
            self.assertIn('v99', msg)
        finally:
            os.unlink(path)

    def test_commit_nack_returns_false(self):
        pack = _make_pack()
        path = _write_bin(pack)
        n = _chunks(pack)
        try:
            hid = _make_hid(
                [(True, _ack_reply(CMD_FONTPACK_BEGIN))] +
                [(True, _ack_reply(CMD_FONTPACK_CHUNK))] * n +
                [(True, _nack_reply(CMD_FONTPACK_COMMIT))]
            )
            ok, msg = flash_fontpack(hid, path)
            self.assertFalse(ok)
            self.assertIn('COMMIT', msg)
        finally:
            os.unlink(path)

    def test_no_apply_step_after_commit(self):
        # COMMIT is terminal for a font pack — there must be no extra send and no
        # reconnect wait (unlike firmware apply).
        pack = _make_pack()
        path = _write_bin(pack)
        try:
            hid = _flash_hid(pack)
            ok, _ = flash_fontpack(hid, path)
            self.assertTrue(ok)
            hid.wait_for_reconnect.assert_not_called()
            self.assertEqual(hid.send_and_read.call_count, 1 + _chunks(pack) + 1)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# flash_fontpack -- cancellation + progress
# ---------------------------------------------------------------------------

class TestFlashFontpackCancellationProgress(unittest.TestCase):

    def test_cancel_mid_stream_sends_cleanup_commit(self):
        pack = _make_pack(body=b'\x42' * (FONTPACK_CHUNK_SIZE * 10))
        path = _write_bin(pack)
        try:
            cancel_flag = [False]
            calls = [0]

            def side_effect(pkt, timeout):
                calls[0] += 1
                if calls[0] == 1:
                    return True, _ack_reply(CMD_FONTPACK_BEGIN)
                if calls[0] == 4:
                    cancel_flag[0] = True
                return True, _ack_reply(CMD_FONTPACK_CHUNK)

            hid = MagicMock()
            hid.send_and_read.side_effect = side_effect
            ok, msg = flash_fontpack(hid, path, cancel_flag=cancel_flag)
            self.assertFalse(ok)
            self.assertIn('cancel', msg.lower())
            self.assertEqual(calls[0], 5)   # BEGIN + 3 chunks + cleanup COMMIT
        finally:
            os.unlink(path)

    def test_progress_starts_0_ends_100(self):
        pack = _make_pack()
        path = _write_bin(pack)
        try:
            hid = _flash_hid(pack)
            pcts = []
            flash_fontpack(hid, path, progress_cb=lambda pct, m: pcts.append(pct))
            self.assertEqual(pcts[0], 0)
            self.assertEqual(pcts[-1], 100)
        finally:
            os.unlink(path)

    def test_progress_never_decreases(self):
        pack = _make_pack(body=b'\xCC' * (FONTPACK_CHUNK_SIZE * 200))
        path = _write_bin(pack)
        try:
            hid = _flash_hid(pack)
            pcts = []
            flash_fontpack(hid, path, progress_cb=lambda pct, m: pcts.append(pct))
            for a, b in zip(pcts, pcts[1:]):
                self.assertLessEqual(a, b)
        finally:
            os.unlink(path)


class TestIdVersionBlock(unittest.TestCase):
    """parse_id_version_block: the per-bundle versions appended to GET_ID (cmd 6)."""

    @staticmethod
    def _reply(name=b"P\x06.Split72 0.8.50 P6 HW2 ", versions=None, pad_to=64):
        raw = bytearray(name) + b"\x00"
        if versions is not None:
            raw += b"V" + bytes([len(versions)])
            for v in versions:
                raw += struct.pack("<H", v)
        raw += b"\x00" * max(0, pad_to - len(raw))
        return bytes(raw)

    def test_parses_versions_in_order(self):
        got = parse_id_version_block(self._reply(versions=[1, 0, 3, 65535, 2, 7]))
        self.assertEqual(got, {0: 1, 1: 0, 2: 3, 3: 65535, 4: 2, 5: 7})

    def test_absent_block_is_empty(self):           # pre-v6 firmware: no 'V' block
        self.assertEqual(parse_id_version_block(self._reply(versions=None)), {})

    def test_fresh_boot_marker_does_not_disturb_block(self):
        r = bytearray(self._reply(versions=[5, 6]))
        r[2] = ord("*")                              # fresh-boot marker on byte 2
        self.assertEqual(parse_id_version_block(bytes(r)), {0: 5, 1: 6})

    def test_truncated_block_is_empty(self):         # count says 4 but bytes run out
        raw = b"P\x06.Split72 0.8.50 P6 HW2 \x00V\x04\x01\x00"
        self.assertEqual(parse_id_version_block(raw), {})


class TestDecideStaleBundles(unittest.TestCase):
    _SHIPPED = [
        {"id": "symbol", "index": 0, "content_version": 2},
        {"id": "emoji",  "index": 5, "content_version": 3},
    ]

    def test_flashes_only_behind(self):
        stale = decide_stale_bundles({0: 2, 5: 1}, self._SHIPPED)
        self.assertEqual([b["id"] for b in stale], ["emoji"])

    def test_missing_index_is_zero(self):            # absent on device == version 0
        stale = decide_stale_bundles({}, self._SHIPPED)
        self.assertEqual([b["index"] for b in stale], [0, 5])

    def test_up_to_date_is_empty(self):
        self.assertEqual(decide_stale_bundles({0: 9, 5: 9}, self._SHIPPED), [])


class TestValidateDoomwad(unittest.TestCase):
    """WHX game-data validation for the doom easter egg install (DOOMWAD target)."""

    def test_valid_whx_accepted(self):
        from polyhost.device.hid_fontpack import validate_doomwad
        ok, msg = validate_doomwad(b"IWHX" + b"\x00" * 100)
        self.assertTrue(ok, msg)

    def test_bad_magic_rejected(self):
        from polyhost.device.hid_fontpack import validate_doomwad
        ok, msg = validate_doomwad(b"IWAD" + b"\x00" * 100)   # a plain WAD is not a WHX
        self.assertFalse(ok)
        self.assertIn("magic", msg)

    def test_too_small_rejected(self):
        from polyhost.device.hid_fontpack import validate_doomwad
        ok, _ = validate_doomwad(b"IWH")
        self.assertFalse(ok)

    def test_too_large_rejected(self):
        from polyhost.device.hid_fontpack import validate_doomwad, DOOMWAD_MAX_SIZE
        ok, msg = validate_doomwad(b"IWHX" + b"\x00" * DOOMWAD_MAX_SIZE)
        self.assertFalse(ok)
        self.assertIn("large", msg)

    def test_doomwad_bundle_id_matches_firmware(self):
        # FONTPACK_BUNDLE_DOOMWAD in qmk base/fw_staging.h — keep in lockstep.
        from polyhost.device.hid_fontpack import DOOMWAD_BUNDLE_ID
        self.assertEqual(DOOMWAD_BUNDLE_ID, 0x7F)


if __name__ == '__main__':
    unittest.main()
