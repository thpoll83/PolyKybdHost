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


if __name__ == "__main__":
    unittest.main()
