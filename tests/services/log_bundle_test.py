import tempfile
import unittest
from unittest import mock
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from polyhost.services import log_bundle as lb


def _line(stamp: datetime, level: str, msg: str) -> str:
    return f"[{stamp.strftime('%Y-%m-%d %H:%M:%S')},{stamp.microsecond // 1000:03d}] {level:<7} {msg}"


class ParseTimestampTest(unittest.TestCase):
    def test_parses_a_formatted_record(self):
        got = lb.parse_timestamp("[2026-08-17 12:34:56,789] INFO    hello")
        self.assertEqual(datetime(2026, 8, 17, 12, 34, 56, 789000), got)

    def test_continuation_line_has_no_timestamp(self):
        self.assertIsNone(lb.parse_timestamp("  File \"x.py\", line 3, in <module>"))

    def test_malformed_timestamp_is_not_a_crash(self):
        self.assertIsNone(lb.parse_timestamp("[2026-13-45 99:99:99,000] INFO x"))


class ParseSinceTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 17, 12, 0, 0)

    def test_units(self):
        for spec, delta in (("30m", timedelta(minutes=30)), ("2h", timedelta(hours=2)),
                            ("7d", timedelta(days=7)), ("1w", timedelta(weeks=1))):
            self.assertEqual(self.now - delta, lb.parse_since(spec, self.now), spec)

    def test_bare_number_means_hours(self):
        self.assertEqual(self.now - timedelta(hours=6), lb.parse_since("6", self.now))

    def test_all_and_empty_mean_no_filter(self):
        for spec in ("all", "", None, "everything"):
            self.assertIsNone(lb.parse_since(spec, self.now))

    def test_garbage_raises(self):
        with self.assertRaises(ValueError):
            lb.parse_since("last tuesday", self.now)

    def test_absurdly_large_value_is_a_ValueError_not_an_OverflowError(self):
        """The regex accepts any number of digits, so timedelta() can overflow.
        Callers only handle ValueError — an OverflowError reaches the user as a
        traceback instead of 'bad input'."""
        for spec in ("99999999999999999999h", "99999999999999999999w"):
            with self.assertRaises(ValueError):
                lb.parse_since(spec, self.now)


class EnvironmentDetailTest(unittest.TestCase):
    """The environment block has to identify the machine, not merely mention it."""

    def test_windows_11_is_not_reported_as_windows_10(self):
        """platform.release() returns "10" on Windows 11 — only the build tells
        them apart, so release alone actively misidentifies the OS."""
        with mock.patch("platform.system", return_value="Windows"), \
             mock.patch("platform.release", return_value="10"), \
             mock.patch("platform.version", return_value="10.0.22631"):
            self.assertIn("Windows 11", lb.os_detail())

    def test_windows_10_stays_windows_10(self):
        with mock.patch("platform.system", return_value="Windows"), \
             mock.patch("platform.release", return_value="10"), \
             mock.patch("platform.version", return_value="10.0.19045"):
            detail = lb.os_detail()
            self.assertIn("Windows 10", detail)
            self.assertNotIn("Windows 11", detail)

    def test_a_malformed_windows_version_does_not_raise(self):
        with mock.patch("platform.system", return_value="Windows"), \
             mock.patch("platform.release", return_value="10"), \
             mock.patch("platform.version", return_value="garbage"):
            self.assertTrue(lb.os_detail())

    def test_macos_reports_its_product_version(self):
        with mock.patch("platform.system", return_value="Darwin"), \
             mock.patch("platform.mac_ver", return_value=("14.5", ("", "", ""), "arm64")):
            self.assertIn("macOS 14.5", lb.os_detail())

    def test_linux_reports_the_distro_not_only_the_kernel(self):
        """A kernel version does not identify a distribution."""
        with mock.patch("platform.system", return_value="Linux"):
            detail = lb.os_detail()
        self.assertTrue(detail)
        self.assertNotEqual(detail, "Linux")

    def test_session_detail_names_the_window_backend(self):
        """XDG_CURRENT_DESKTOP/XDG_SESSION_TYPE select the backend, so a Linux
        report is not diagnosable without them."""
        with mock.patch("platform.system", return_value="Linux"):
            with mock.patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "KDE",
                                                "XDG_SESSION_TYPE": "x11"}):
                self.assertIn("kde_win_reporter", lb.session_detail())
            with mock.patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "GNOME",
                                                "XDG_SESSION_TYPE": "wayland"}):
                self.assertIn("gnome_wayland_reporter", lb.session_detail())
            with mock.patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "GNOME",
                                                "XDG_SESSION_TYPE": "x11"}):
                self.assertIn("pywinctl", lb.session_detail())

    def test_session_detail_is_linux_only(self):
        for system in ("Windows", "Darwin"):
            with mock.patch("platform.system", return_value=system):
                self.assertIsNone(lb.session_detail())

    def test_environment_text_carries_version_os_and_arch(self):
        text = lb.environment_text()
        self.assertIn("PolyHost version", text)
        self.assertIn("OS ", text)
        self.assertIn("Host protocol", text)

    def test_slow_probes_are_opt_in(self):
        """The autostart probe shells out on Windows, so a GUI-thread caller
        must be able to leave it out."""
        with mock.patch.object(lb, "autostart_detail",
                               return_value="scheduled task (at logon)") as probe:
            self.assertNotIn("Autostart", lb.environment_text())
            probe.assert_not_called()
            self.assertIn("Autostart", lb.environment_text(include_slow=True))

    def test_a_failing_autostart_probe_is_not_fatal(self):
        with mock.patch("polyhost.services.add_to_startup.get_autostart_status",
                        side_effect=OSError("nope")):
            self.assertIsNone(lb.autostart_detail())


class SliceLinesTest(unittest.TestCase):
    def setUp(self):
        self.t0 = datetime(2026, 8, 17, 10, 0, 0)

    def test_keeps_only_lines_at_or_after_cutoff(self):
        lines = [_line(self.t0 + timedelta(minutes=i), "INFO", f"m{i}") for i in range(5)]
        kept = lb.slice_lines(lines, self.t0 + timedelta(minutes=3))
        self.assertEqual(["m3", "m4"], [l.split()[-1] for l in kept])

    def test_continuation_lines_follow_their_record(self):
        """A traceback belongs to the ERROR line above it — dropping the
        untimestamped continuation keeps the half that says nothing."""
        lines = [
            _line(self.t0, "ERROR", "old boom"),
            "Traceback (most recent call last):",
            "  old detail",
            _line(self.t0 + timedelta(hours=2), "ERROR", "new boom"),
            "Traceback (most recent call last):",
            "  new detail",
        ]
        kept = lb.slice_lines(lines, self.t0 + timedelta(hours=1))
        self.assertEqual(3, len(kept))
        self.assertIn("new boom", kept[0])
        self.assertIn("new detail", kept[2])
        self.assertNotIn("  old detail", kept)

    def test_leading_untimestamped_lines_are_dropped(self):
        lines = ["  orphan continuation", _line(self.t0, "INFO", "first")]
        kept = lb.slice_lines(lines, self.t0 - timedelta(minutes=1))
        self.assertEqual(1, len(kept))

    def test_no_cutoff_keeps_everything(self):
        lines = ["anything", "at all"]
        self.assertEqual(lines, lb.slice_lines(lines, None))


class RedactionTest(unittest.TestCase):
    def test_masks_active_window_title_but_keeps_app_name(self):
        line = ('Active App Changed: "chrome.exe", Title: "Q3 layoffs — Chrome"  Handle: 42')
        out = lb.redact_text(line)
        self.assertNotIn("Q3 layoffs", out)
        self.assertIn("chrome.exe", out)
        self.assertIn("Handle: 42", out)
        self.assertIn("<redacted:19 chars>", out)

    def test_masks_mapping_mismatch_title(self):
        out = lb.redact_text("App 'code' in mapping but title did not match (title='secret.md - VS Code')")
        self.assertNotIn("secret.md", out)
        self.assertIn("App 'code' in mapping", out)

    def test_masks_report_window_title(self):
        out = lb.redact_text("report_window: handle=7 name=excel title=Payroll 2026.xlsx os=windows")
        self.assertNotIn("Payroll", out)
        self.assertIn("name=excel", out)
        self.assertIn("os=windows", out)

    def test_masks_both_sides_of_a_stored_title_diff(self):
        out = lb.redact_text(
            "remote_changed: no change (ip=1.2.3.4 stored_handle=1->1 stored_title=Alpha->Beta os=win)")
        self.assertNotIn("Alpha", out)
        self.assertNotIn("Beta", out)

    def test_leaves_ordinary_lines_alone(self):
        line = '[2026-08-17 12:00:00,000] INFO    Connected: "PolyKybd Split72" protocol 11'
        self.assertEqual(line, lb.redact_text(line))

    def test_settings_secrets_are_masked_but_empty_stays_empty(self):
        raw = ("browser_report_token: hunter2\n"
               "telemetry_install_id: 9f2c-uuid\n"
               "daemon_mode: true\n")
        out = lb.redact_settings(raw)
        self.assertNotIn("hunter2", out)
        self.assertNotIn("9f2c-uuid", out)
        self.assertIn("daemon_mode: true", out)
        self.assertIn("browser_report_token: ''", lb.redact_settings("browser_report_token: ''\n"))


class DiscoveryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_rotation_chain_is_oldest_first(self):
        """RotatingFileHandler shifts the live file to .1, so .3 is the OLDEST —
        reading base-first would emit the concatenation backwards."""
        for name in ("host_log.txt", "host_log.txt.1", "host_log.txt.2"):
            (self.dir / name).write_text("x", encoding="utf-8")
        chain = lb.discover(self.dir)["host"]
        self.assertEqual(["host_log.txt.2", "host_log.txt.1", "host_log.txt"],
                         [p.name for p in chain])

    def test_only_existing_sources_are_reported(self):
        (self.dir / "daemon_log.txt").write_text("x", encoding="utf-8")
        self.assertEqual(["daemon"], list(lb.discover(self.dir)))


class BundleTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.t0 = datetime.now() - timedelta(hours=48)
        (self.dir / "host_log.txt.1").write_text(
            _line(self.t0, "INFO", "ancient") + "\n", encoding="utf-8")
        (self.dir / "host_log.txt").write_text("\n".join([
            _line(datetime.now() - timedelta(hours=30), "INFO", "yesterdayish"),
            _line(datetime.now() - timedelta(minutes=5), "INFO",
                  'Active App Changed: "excel.exe", Title: "Payroll.xlsx"  Handle: 9'),
        ]) + "\n", encoding="utf-8")
        (self.dir / "daemon_log.txt").write_text(
            _line(datetime.now() - timedelta(minutes=1), "INFO", "daemon alive") + "\n",
            encoding="utf-8")

    def _build(self, **kw):
        dest = self.dir / "out.zip"
        return lb.build_bundle(dest, log_dir=self.dir, **kw), dest

    def test_bundle_contains_logs_diagnostics_and_readme(self):
        result, dest = self._build()
        with zipfile.ZipFile(dest) as zf:
            names = set(zf.namelist())
            self.assertIn("README.txt", names)
            self.assertIn("diagnostics.txt", names)
            self.assertIn("logs/host.txt", names)
            self.assertIn("logs/daemon.txt", names)
        self.assertEqual(2, len([s for s in result.sources if s.lines]))

    def test_since_excludes_older_lines(self):
        result, dest = self._build(since=lb.parse_since("24h"))
        with zipfile.ZipFile(dest) as zf:
            host = zf.read("logs/host.txt").decode()
        self.assertNotIn("ancient", host)
        self.assertNotIn("yesterdayish", host)
        self.assertIn("Payroll.xlsx", host)
        self.assertIsNotNone(result.since)

    def test_redaction_flag_masks_titles_in_the_zip(self):
        _, dest = self._build(redact=True)
        with zipfile.ZipFile(dest) as zf:
            host = zf.read("logs/host.txt").decode()
            readme = zf.read("README.txt").decode()
        self.assertNotIn("Payroll.xlsx", host)
        self.assertIn("excel.exe", host)
        self.assertIn("masked", readme)

    def test_readme_warns_when_titles_are_included(self):
        _, dest = self._build(redact=False)
        with zipfile.ZipFile(dest) as zf:
            self.assertIn("NONE", zf.read("README.txt").decode())

    def test_caller_diagnostics_are_included(self):
        _, dest = self._build(diagnostics="Keyboard: PolyKybd Split72")
        with zipfile.ZipFile(dest) as zf:
            diag = zf.read("diagnostics.txt").decode()
        self.assertIn("PolyKybd Split72", diag)
        self.assertIn("PolyHost version", diag)  # env block always appended

    def test_empty_log_dir_raises(self):
        empty = self.dir / "empty"
        empty.mkdir()
        with self.assertRaises(lb.LogBundleError):
            lb.build_bundle(empty / "out.zip", log_dir=empty)

    def test_unreadable_rotation_file_does_not_abort(self):
        """One locked backup must not cost the user the rest of the bundle."""
        bad = self.dir / "startup_log.txt"
        bad.mkdir()  # a directory where a file is expected → OSError on open
        result, dest = self._build()
        self.assertTrue(dest.exists())
        self.assertIn("host", [s.label for s in result.sources])


class RecentTextTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_caps_lines_per_source_and_keeps_the_tail(self):
        now = datetime.now()
        (self.dir / "host_log.txt").write_text("\n".join(
            _line(now, "INFO", f"m{i}") for i in range(50)) + "\n", encoding="utf-8")
        out = lb.recent_text(self.dir, max_lines=10)
        self.assertIn("m49", out)
        self.assertNotIn("m39", out)
        self.assertIn("last 10 lines", out)

    def test_no_content_is_stated_not_empty(self):
        self.assertIn("no log content", lb.recent_text(self.dir))


def _marker(what: str, pid: int, stamp: datetime) -> str:
    """A crash_log._stamp() line, byte-for-byte as the writer emits it."""
    return f"=== {what} | pid {pid} | {stamp.strftime('%Y-%m-%d %H:%M:%S')} ==="


class CrashLogSourceTest(unittest.TestCase):
    """crash_log.txt is collectable at all, and is never time-sliced.

    It was written by util/crash_log.py but registered nowhere, so the one
    artifact that proves whether the app crashed could be neither collected nor
    viewed. Registering it is only half the fix: its lines do not carry the
    `[YYYY-MM-DD HH:MM:SS,mmm]` prefix slice_lines keys off, so a naive
    registration would have produced a permanently EMPTY section — the same
    bug in a new costume.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.old = datetime.now() - timedelta(days=3)

    def _write(self, *lines):
        (self.dir / "crash_log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_the_source_is_registered(self):
        labels = [s.label for s in lb.LOG_SOURCES]
        self.assertIn("crash", labels)

    def test_the_filename_comes_from_the_writer(self):
        """A literal here could drift from the file crash_log actually opens."""
        from polyhost.util import crash_log
        source = next(s for s in lb.LOG_SOURCES if s.label == "crash")
        self.assertEqual(crash_log.CRASH_LOG, source.filename)

    def test_it_is_declared_unsliced(self):
        source = next(s for s in lb.LOG_SOURCES if s.label == "crash")
        self.assertFalse(source.sliced)

    def test_every_other_source_is_still_sliced(self):
        for source in lb.LOG_SOURCES:
            if source.label != "crash":
                self.assertTrue(source.sliced, source.label)

    def test_old_crash_content_survives_a_narrow_window(self):
        """The regression that makes registration meaningful: none of these
        lines carries a sliceable timestamp, so under slicing all of them are
        dropped and the section silently disappears."""
        self._write(_marker("session start", 42, self.old),
                    "Fatal Python error: Segmentation fault",
                    "Current thread 0x00007f1a (most recent call first):",
                    '  File "polyhost/host.py", line 1, in <module>')
        out = lb.collect_text(self.dir, since=datetime.now() - timedelta(hours=1))
        self.assertIn("crash", out)
        self.assertIn("Segmentation fault", out["crash"])

    def test_a_native_dump_is_kept_even_though_it_has_no_marker(self):
        """faulthandler writes on the fault with no marker of its own, so under
        slicing it would inherit the decision of a much older session start."""
        self._write("Current thread 0x00007f1a (most recent call first):",
                    '  File "polyhost/gui/host.py", line 9, in paintEvent')
        out = lb.collect_text(self.dir, since=datetime.now())
        self.assertIn("paintEvent", out["crash"])

    def test_a_normal_log_is_still_sliced(self):
        """The exemption must not have leaked into the other sources."""
        (self.dir / "host_log.txt").write_text(
            _line(self.old, "INFO", "ancient") + "\n", encoding="utf-8")
        out = lb.collect_text(self.dir, since=datetime.now() - timedelta(hours=1))
        self.assertNotIn("host", out)

    def test_it_reaches_the_bug_report_bundle(self):
        """The user-visible point: Report a Problem attaches build_bundle's zip,
        so registration is what puts the crash evidence in front of a maintainer."""
        self._write(_marker("session start", 7, self.old),
                    _marker("unhandled exception: KeyError: 'boom'", 7, self.old))
        dest = self.dir / "report.zip"
        lb.build_bundle(dest, log_dir=self.dir, since=datetime.now() - timedelta(hours=1))
        with zipfile.ZipFile(dest) as z:
            names = z.namelist()
            crash = [n for n in names if "crash" in n]
            self.assertTrue(crash, names)
            self.assertIn("KeyError", z.read(crash[0]).decode("utf-8"))


class CrashSummaryTest(unittest.TestCase):
    """The one-liner the report BODY carries, so the evidence is visible
    without opening the attachment."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.t = datetime(2026, 8, 18, 7, 30, 0)

    def _write(self, *lines):
        (self.dir / "crash_log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_no_file_is_reported_as_nothing(self):
        self.assertIsNone(lb.crash_summary(self.dir))

    def test_counts_sessions_and_clean_exits(self):
        self._write(_marker("session start", 1, self.t),
                    _marker("clean exit (Qt event loop, rc=0)", 1, self.t))
        got = lb.crash_summary(self.dir)
        self.assertIn("1 session(s)", got)
        self.assertIn("1 clean exit(s)", got)

    def test_counts_unhandled_exceptions(self):
        self._write(_marker("session start", 1, self.t),
                    _marker("unhandled exception: KeyError: 'x'", 1, self.t))
        self.assertIn("1 unhandled exception(s)", lb.crash_summary(self.dir))

    def test_counts_native_fault_dumps(self):
        self._write(_marker("session start", 1, self.t),
                    "Fatal Python error: Segmentation fault")
        self.assertIn("1 native fault dump(s)", lb.crash_summary(self.dir))

    def test_one_dump_is_counted_once_not_per_line(self):
        """A fatal signal prints BOTH a 'Fatal Python error' line and a
        'Current thread' line; counting each reported one crash as two (caught
        by running the real CLI, not by the test above)."""
        self._write(_marker("session start", 1, self.t),
                    "Fatal Python error: Segmentation fault",
                    "",
                    "Current thread 0x00007f1a (most recent call first):",
                    '  File "polyhost/host.py", line 12, in paintEvent')
        self.assertIn("1 native fault dump(s)", lb.crash_summary(self.dir))

    def test_two_dumps_in_separate_sessions_are_counted_separately(self):
        self._write(_marker("session start", 1, self.t),
                    "Current thread 0x00007f1a (most recent call first):",
                    _marker("session start", 2, self.t),
                    "Current thread 0x00007f2b (most recent call first):")
        self.assertIn("2 native fault dump(s)", lb.crash_summary(self.dir))

    def test_a_healthy_log_makes_no_crash_claim(self):
        """A live GUI and a live daemon each have an unmatched session start, so
        a 'it crashed' verdict here would fire on every healthy report."""
        self._write(_marker("session start", 1, self.t),
                    _marker("session start", 2, self.t))
        got = lb.crash_summary(self.dir).lower()
        for word in ("crash", "died", "unclean", "unhandled", "fault"):
            self.assertNotIn(word, got)

    def test_it_appears_in_the_diagnostics_block(self):
        self._write(_marker("session start", 1, self.t))
        with mock.patch.object(lb, "default_log_dir", return_value=self.dir):
            self.assertIn("Crash log", lb.environment_text())

    def test_a_failing_summary_never_breaks_the_diagnostics(self):
        with mock.patch.object(lb, "crash_summary", side_effect=OSError("nope")):
            self.assertIn("PolyHost version", lb.environment_text())


class ViewerFilesTest(unittest.TestCase):
    """The GUI log-viewer tabs are DERIVED from LOG_SOURCES.

    Both tray apps used to hand-build this dict and they drifted: the
    forwarder's was missing the crash log entirely. One declaration now feeds
    the bundle, the clipboard text and both viewers.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_always_sources_appear_even_before_the_file_exists(self):
        got = lb.viewer_files(always=("host",), log_dir=self.dir)
        self.assertEqual({"PolyHost Log": str(self.dir / "host_log.txt")}, got)

    def test_other_sources_appear_only_once_they_exist(self):
        self.assertNotIn("Crash Log", lb.viewer_files(log_dir=self.dir))
        (self.dir / "crash_log.txt").write_text("x", encoding="utf-8")
        self.assertEqual(str(self.dir / "crash_log.txt"),
                         lb.viewer_files(log_dir=self.dir)["Crash Log"])

    def test_the_crash_log_reaches_BOTH_apps_tab_lists(self):
        """The drift this whole change exists to fix."""
        (self.dir / "crash_log.txt").write_text("x", encoding="utf-8")
        host = lb.viewer_files(always=("host", "keyboard-console"), log_dir=self.dir)
        forwarder = lb.viewer_files(always=("forwarder",), log_dir=self.dir)
        self.assertIn("Crash Log", host)
        self.assertIn("Crash Log", forwarder)

    def test_every_source_carries_a_viewer_title(self):
        """A source with no title is invisible in the viewers — if one is ever
        added deliberately, this test is the place to say so."""
        for source in lb.LOG_SOURCES:
            self.assertTrue(source.title, source.label)

    def test_both_apps_call_it_rather_than_building_a_dict(self):
        import pathlib as _pl
        import polyhost
        root = _pl.Path(polyhost.__file__).parent
        for name in ("host.py", "forwarder.py"):
            src = (root / name).read_text(encoding="utf-8")
            with self.subTest(module=name):
                self.assertIn("log_bundle.viewer_files(", src)
                self.assertNotIn('log_files["Crash Log"]', src)


class CrashMarkerFormatTest(unittest.TestCase):
    """The marker format lives with the WRITER; the collector imports it.

    A second hand-written copy in log_bundle would not raise on drift — it would
    match nothing and report a confidently wrong "0 session(s)".
    """

    def test_the_writer_and_the_reader_agree(self):
        from polyhost.util import crash_log
        line = crash_log.format_marker("session start", 4242)
        what, pid, ts = crash_log.parse_marker(line)
        self.assertEqual("session start", what)
        self.assertEqual(4242, pid)
        self.assertRegex(ts, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_a_real_stamp_write_round_trips(self):
        """Goes through _stamp(), the function that actually writes the file —
        not a re-typed format string."""
        from polyhost.util import crash_log
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "crash_log.txt"
        with open(path, "w", encoding="utf-8") as f:
            with mock.patch.object(crash_log, "_crash_file", f):
                crash_log._stamp("clean exit (Qt event loop, rc=0)")
        line = path.read_text(encoding="utf-8").strip()
        parsed = crash_log.parse_marker(line)
        self.assertIsNotNone(parsed, line)
        self.assertEqual("clean exit (Qt event loop, rc=0)", parsed[0])

    def test_a_non_marker_line_is_not_parsed(self):
        from polyhost.util import crash_log
        self.assertIsNone(crash_log.parse_marker("Fatal Python error: Segfault"))


class ReviewRegressionTest(unittest.TestCase):
    """Three findings from the CodeRabbit review on #178, all reproduced first."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self._other = tempfile.TemporaryDirectory()
        self.other = Path(self._other.name)
        self.addCleanup(self._other.cleanup)

    def test_the_bundle_summarises_the_crash_log_it_actually_ships(self):
        """build_bundle(log_dir=X) zipped X's logs while diagnostics.txt
        summarised default_log_dir()'s crash log — a report whose body and
        attachment describe different machines' state."""
        (self.dir / "crash_log.txt").write_text(
            "=== session start | pid 7 | 2026-08-15 09:00:00 ===\n", encoding="utf-8")
        # A DIFFERENT directory is what default_log_dir() would pick.
        (self.other / "crash_log.txt").write_text(
            "=== session start | pid 9 | 2026-01-01 00:00:00 ===\n"
            "=== session start | pid 9 | 2026-01-01 00:00:01 ===\n"
            "=== session start | pid 9 | 2026-01-01 00:00:02 ===\n", encoding="utf-8")
        dest = self.dir / "b.zip"
        with mock.patch.object(lb, "default_log_dir", return_value=self.other):
            lb.build_bundle(dest, log_dir=self.dir, since=None)
        with zipfile.ZipFile(dest) as z:
            diag = z.read("diagnostics.txt").decode("utf-8")
            shipped = z.read("logs/crash.txt").decode("utf-8")
        self.assertIn("pid 7", shipped)
        self.assertIn("1 session(s)", diag)      # the shipped file, not the other
        self.assertNotIn("3 session(s)", diag)

    def test_viewer_files_returns_paths_the_viewer_can_actually_open(self):
        """viewer_files() checked existence in default_log_dir() but returned
        bare names, which LogViewerDialog opens relative to the cwd. When those
        differ the viewer shows the wrong file or fails to load it."""
        (self.other / "crash_log.txt").write_text("marker", encoding="utf-8")
        with mock.patch.object(lb, "default_log_dir", return_value=self.other):
            files = lb.viewer_files(always=("forwarder",))
        for title, path in files.items():
            with self.subTest(tab=title):
                self.assertTrue(Path(path).is_absolute(), f"{title}: {path!r}")
        # And the one that exists must be openable as given, from anywhere.
        self.assertEqual("marker",
                         Path(files["Crash Log"]).read_text(encoding="utf-8"))


class MultilineMarkerTest(unittest.TestCase):
    """A marker whose `what` spans lines cannot be parsed back.

    `_stamp()` interpolates `str(exc)` into the marker, and plenty of exception
    messages contain newlines. The marker then occupies several physical lines,
    MARKER_RE (anchored) matches none of them, and crash_summary silently omits
    that exception — an undercount in the one line of the report that is
    supposed to say a crash happened.
    """

    def test_a_multiline_exception_message_still_round_trips(self):
        from polyhost.util import crash_log
        line = crash_log.format_marker(
            "unhandled exception: ValueError: first line\nsecond line", 99)
        self.assertEqual(1, len(line.splitlines()))
        parsed = crash_log.parse_marker(line)
        self.assertIsNotNone(parsed, line)
        self.assertIn("first line", parsed[0])
        self.assertIn("second line", parsed[0])

    def test_carriage_returns_are_normalised_too(self):
        from polyhost.util import crash_log
        line = crash_log.format_marker("thread exception: a\r\nb", 1)
        self.assertEqual(1, len(line.splitlines()))
        self.assertIsNotNone(crash_log.parse_marker(line))

    def test_an_empty_what_still_produces_a_parseable_marker(self):
        from polyhost.util import crash_log
        parsed = crash_log.parse_marker(crash_log.format_marker("", 1))
        self.assertIsNotNone(parsed)

    def test_such_an_exception_is_counted_in_the_summary(self):
        """The user-visible consequence: the report body must not undercount."""
        from polyhost.util import crash_log
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        (d / "crash_log.txt").write_text(
            crash_log.format_marker("session start", 5) + "\n"
            + crash_log.format_marker(
                "unhandled exception: ValueError: broke\nbadly", 5) + "\n",
            encoding="utf-8")
        self.assertIn("1 unhandled exception(s)", lb.crash_summary(d))


if __name__ == "__main__":
    unittest.main()
