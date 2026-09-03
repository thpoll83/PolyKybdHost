"""crash_report — parsing the firmware's console line, decoding the HID record,
reassembling report-sized console fragments, and the text handed to humans."""
import struct
import unittest

from polyhost.services import crash_report as cr

LINE = ("crash: side=master kind=hardfault core=0 pc=0x10012345 lr=0x1000abcd "
        "sp=0x20040ff0 psr=0x21000003 icsr=0x00000003 phase=3:0x0015 "
        "up=123456ms n=1 reason=0x22 fw=0.18.0")


def _record_bytes(*, magic=cr.RECORD_MAGIC, kind=1, core=0, consecutive=1, reason=0x22,
                  pc=0x10012345, lr=0x1000abcd, sp=0x20040FF0, xpsr=0x21000003,
                  icsr=3, uptime=123456, phase=3, phase_arg=0x15, fw=b"0.18.0"):
    return cr.RECORD_STRUCT.pack(magic, kind, core, consecutive, reason, pc, lr, sp,
                                 xpsr, icsr, uptime, phase, phase_arg,
                                 fw.ljust(8, b"\x00"), 0xDEADBEEF)


class ParseLineTest(unittest.TestCase):
    def test_the_firmware_line_parses_field_for_field(self):
        rec = cr.parse_crash_line("   " + LINE)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.side, "master")
        self.assertEqual(rec.kind, "hardfault")
        self.assertEqual(rec.pc, 0x10012345)
        self.assertEqual(rec.lr, 0x1000ABCD)
        self.assertEqual(rec.sp, 0x20040FF0)
        self.assertEqual(rec.xpsr, 0x21000003)
        self.assertEqual(rec.phase, 3)
        self.assertEqual(rec.phase_arg, 0x15)
        self.assertEqual(rec.uptime_ms, 123456)
        self.assertEqual(rec.consecutive, 1)
        self.assertEqual(rec.reset_reason, 0x22)
        self.assertEqual(rec.fw, "0.18.0")
        self.assertEqual(rec.phase_name, "HID command")
        self.assertEqual(rec.vector, 3)
        self.assertIn("watchdog forced", rec.reset_reason_text)
        self.assertIn("RUN pin", rec.reset_reason_text)
        # The stored line is the firmware's own, stripped of the banner indent.
        self.assertEqual(rec.line, LINE)

    def test_an_ordinary_console_line_is_not_a_record(self):
        self.assertIsNone(cr.parse_crash_line("Split link: 12 tx crc_err=0"))
        self.assertIsNone(cr.parse_crash_line("crash: side=master kind=hardfault"))

    def test_console_line_round_trips_through_the_dict_and_back(self):
        rec = cr.parse_crash_line(LINE)
        again = cr.CrashRecord.from_dict(rec.to_dict())
        self.assertEqual(again, rec)
        self.assertEqual(again.as_console_line(), LINE)


class DecodeRecordTest(unittest.TestCase):
    def test_struct_is_48_bytes_like_poly_crash_record_t(self):
        self.assertEqual(cr.RECORD_LEN, 48)
        self.assertEqual(cr.HID_BODY_LEN, 49)

    def test_decodes_a_present_fresh_record(self):
        body = bytes([cr.HID_FLAG_PRESENT | cr.HID_FLAG_FRESH]) + _record_bytes()
        rec = cr.decode_record(body, "slave")
        self.assertIsNotNone(rec)
        self.assertEqual(rec.side, "slave")
        self.assertEqual(rec.kind, "hardfault")
        self.assertTrue(rec.fresh)
        self.assertEqual(rec.fw, "0.18.0")
        # A decoded record prints the same line shape the console would carry.
        self.assertEqual(rec.as_console_line().replace("side=slave", "side=master"), LINE)

    def test_archived_record_is_not_fresh(self):
        body = bytes([cr.HID_FLAG_PRESENT]) + _record_bytes()
        self.assertFalse(cr.decode_record(body).fresh)

    def test_absent_flag_short_body_and_bad_magic_all_decode_to_none(self):
        self.assertIsNone(cr.decode_record(bytes([0]) + _record_bytes()))
        self.assertIsNone(cr.decode_record(bytes([1]) + _record_bytes()[:-1]))
        self.assertIsNone(cr.decode_record(bytes([1]) + _record_bytes(magic=0)))
        self.assertIsNone(cr.decode_record(b""))

    def test_unknown_kind_is_named_not_dropped(self):
        body = bytes([1]) + _record_bytes(kind=9)
        self.assertEqual(cr.decode_record(body).kind, "kind 9")


class ScannerTest(unittest.TestCase):
    def test_a_line_split_across_two_reads_is_reassembled(self):
        s = cr.CrashScanner()
        cut = len(LINE) // 2
        self.assertEqual(s.feed("boot ok\n   " + LINE[:cut]), [])
        recs = s.feed(LINE[cut:] + "\nnext line\n")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].line, LINE)

    def test_an_unterminated_line_is_not_reported_yet(self):
        s = cr.CrashScanner()
        self.assertEqual(s.feed(LINE), [])
        self.assertEqual(len(s.feed("\n")), 1)

    def test_banner_re_emits_are_reported_once(self):
        s = cr.CrashScanner()
        self.assertEqual(len(s.feed(LINE + "\n")), 1)
        self.assertEqual(s.feed(LINE + "\n" + LINE + "\n"), [])
        # A different record (the slave's) is new.
        slave = LINE.replace("side=master", "side=slave")
        self.assertEqual(len(s.feed(slave + "\n")), 1)

    def test_forget_lets_the_same_line_through_again(self):
        s = cr.CrashScanner()
        s.feed(LINE + "\n")
        s.forget()
        self.assertEqual(len(s.feed(LINE + "\n")), 1)

    def test_empty_and_unrelated_chunks_yield_nothing(self):
        s = cr.CrashScanner()
        self.assertEqual(s.feed(""), [])
        self.assertEqual(s.feed("LoopProf: ...\nSplit link: 1 tx\n"), [])

    def test_a_runaway_fragment_is_bounded(self):
        s = cr.CrashScanner()
        s.feed("x" * (cr.CrashScanner.MAX_PENDING * 3))
        self.assertLessEqual(len(s._pending), cr.CrashScanner.MAX_PENDING)


class TextTest(unittest.TestCase):
    def test_summary_is_readable_and_names_the_phase_and_command(self):
        text = cr.summarize(cr.parse_crash_line(LINE))
        self.assertIn("HardFault", text)
        self.assertIn("HID command", text)
        self.assertIn("(HID command 21)", text)
        self.assertIn("123.5 s", text)
        self.assertIn("0x10012345", text)
        self.assertIn("addr2line", text)

    def test_report_text_carries_the_raw_line_and_diagnostics(self):
        rec = cr.parse_crash_line(LINE)
        text = cr.compose_report_text([rec], "PolyKybdHost 1.2.3\nOS: x", "1.2.3")
        self.assertIn(LINE, text)
        self.assertIn("Diagnostics:", text)
        self.assertIn("OS: x", text)
        self.assertIn("PolyKybdHost 1.2.3", text)
        self.assertTrue(text.endswith("\n"))

    def test_issue_pieces(self):
        rec = cr.parse_crash_line(LINE)
        self.assertEqual(cr.issue_title([rec]),
                         "Firmware crash: hardfault on master (0.18.0) in HID command")
        body = cr.issue_description([rec])
        self.assertIn("```\n" + LINE + "\n```", body)
        self.assertIn("What I was doing", body)


if __name__ == "__main__":
    unittest.main()
