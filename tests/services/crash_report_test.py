"""crash_report — parsing the firmware's console line, decoding the HID record,
reassembling report-sized console fragments, and the text handed to humans."""
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
        self.assertLessEqual(len(s._lines._pending), cr.CrashScanner.MAX_PENDING)


class KeyTest(unittest.TestCase):
    """The console copy and the cmd 39 copy of one crash must be ONE record."""

    def test_console_and_hid_copies_of_one_crash_share_a_key(self):
        console = cr.parse_crash_line("   " + LINE)
        hid = cr.decode_record(bytes([cr.HID_FLAG_PRESENT | cr.HID_FLAG_FRESH])
                               + _record_bytes(), "master")
        self.assertEqual(hid.line, "")
        self.assertEqual(console.key(), hid.key())
        self.assertEqual(console.key(), LINE)

    def test_the_key_ignores_whatever_surrounded_the_console_line(self):
        rec = cr.parse_crash_line("[12.345] " + LINE)
        self.assertEqual(rec.key(), LINE)

    def test_a_different_half_is_a_different_key(self):
        body = bytes([cr.HID_FLAG_PRESENT]) + _record_bytes()
        self.assertNotEqual(cr.decode_record(body, "master").key(),
                            cr.decode_record(body, "slave").key())

    def test_note_dedupes_across_sources(self):
        s = cr.CrashScanner()
        hid = cr.decode_record(bytes([cr.HID_FLAG_PRESENT | cr.HID_FLAG_FRESH])
                               + _record_bytes(), "master")
        self.assertTrue(s.note(hid))
        self.assertFalse(s.note(hid))
        # The banner line for the same crash, arriving after the HID read.
        self.assertEqual(s.feed(LINE + "\n"), [])

    def test_a_console_record_blocks_the_later_hid_copy(self):
        s = cr.CrashScanner()
        self.assertEqual(len(s.feed(LINE + "\n")), 1)
        hid = cr.decode_record(bytes([cr.HID_FLAG_PRESENT | cr.HID_FLAG_FRESH])
                               + _record_bytes(), "master")
        self.assertFalse(s.note(hid))


class BootBreadcrumbTest(unittest.TestCase):
    def test_the_field_record_reads_as_the_75_percent_panel_paint(self):
        # fw 1.3.2, 2026-10-02: the screen froze at "63%, 4 / 4".
        self.assertEqual(cr.boot_breadcrumb_text(0x16E1),
                         "boot step 6, status panel paint did not finish (before its first "
                         "render call on firmware with per-call marks); core1 running")

    def test_each_range(self):
        self.assertEqual(cr.boot_breadcrumb_text(0x0005), "boot step 5")
        self.assertEqual(cr.boot_breadcrumb_text(0x0504),
                         "boot step 5, sub-step or render key 4")
        self.assertEqual(cr.boot_breadcrumb_text(0x15B3),
                         "boot step 5, sub-step 4 status panel paint, render call 4; core1 running")
        self.assertEqual(cr.boot_breadcrumb_text(0x16C2),
                         "boot step 6 status panel paint, render call 3; core1 running")
        self.assertEqual(cr.boot_breadcrumb_text(0x05E2),
                         "boot step 5, keycap logo draw did not finish; core1 not yet running")
        self.assertEqual(cr.boot_breadcrumb_text(0x06F0), "boot step 6, breadcrumb 0x06f0")
        # Unassigned, and NOT a render key: keys are 1..40.
        self.assertEqual(cr.boot_breadcrumb_text(0x16D2), "boot step 6, breadcrumb 0x16d2")

    def test_the_summary_carries_it(self):
        rec = cr.parse_crash_line(LINE.replace("kind=hardfault", "kind=watchdog")
                                  .replace("phase=3:0x0015", "phase=1:0x16e1"))
        self.assertIn("boot (boot step 6, status panel paint did not finish",
                      cr.summarize(rec))


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
