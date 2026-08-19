"""`polyctl logs` must work with NO host running — that is the whole point.

The other subcommands drive the device and legitimately fail when nothing is
listening; log collection reads files, and the moment a user most needs it is
the one where the app failed to start or the daemon died.
"""
import io
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from polyhost.cli import polyctl


def _line(stamp: datetime, msg: str) -> str:
    return f"[{stamp.strftime('%Y-%m-%d %H:%M:%S')},000] INFO    {msg}"


class PolyctlLogsOfflineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        now = datetime.now()
        (self.dir / "host_log.txt").write_text("\n".join([
            _line(now - timedelta(hours=40), "ancient"),
            _line(now - timedelta(minutes=3), 'Active App Changed: "excel.exe", '
                                              'Title: "Payroll.xlsx"  Handle: 9'),
        ]) + "\n", encoding="utf-8")

    def _run(self, *argv):
        """Run polyctl.main with connect() failing, as it does with no host."""
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(polyctl, "connect",
                               side_effect=ConnectionRefusedError("nothing listening")):
            with redirect_stdout(out), redirect_stderr(err):
                code = polyctl.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_paths_works_without_a_running_host(self):
        code, out, _ = self._run("logs", "paths", "--log-dir", str(self.dir))
        self.assertEqual(0, code)
        self.assertIn("host_log.txt", out)

    def test_bundle_works_without_a_running_host(self):
        dest = self.dir / "b.zip"
        code, out, _ = self._run("logs", "bundle", "--log-dir", str(self.dir),
                                 "-o", str(dest))
        self.assertEqual(0, code)
        self.assertTrue(dest.exists())
        with zipfile.ZipFile(dest) as zf:
            self.assertIn("logs/host.txt", zf.namelist())
        self.assertIn("wrote", out)

    def test_bundle_warns_when_titles_are_not_redacted(self):
        code, out, _ = self._run("logs", "bundle", "--log-dir", str(self.dir),
                                 "-o", str(self.dir / "b.zip"))
        self.assertEqual(0, code)
        self.assertIn("window titles are included", out)

    def test_redact_masks_titles_and_drops_the_warning(self):
        dest = self.dir / "r.zip"
        code, out, _ = self._run("logs", "bundle", "--redact",
                                 "--log-dir", str(self.dir), "-o", str(dest))
        self.assertEqual(0, code)
        self.assertNotIn("window titles are included", out)
        with zipfile.ZipFile(dest) as zf:
            self.assertNotIn("Payroll.xlsx", zf.read("logs/host.txt").decode())

    def test_default_since_is_24h(self):
        dest = self.dir / "d.zip"
        self._run("logs", "bundle", "--log-dir", str(self.dir), "-o", str(dest))
        with zipfile.ZipFile(dest) as zf:
            self.assertNotIn("ancient", zf.read("logs/host.txt").decode())

    def test_since_all_includes_older_lines(self):
        dest = self.dir / "a.zip"
        self._run("logs", "bundle", "--since", "all", "--log-dir", str(self.dir),
                  "-o", str(dest))
        with zipfile.ZipFile(dest) as zf:
            self.assertIn("ancient", zf.read("logs/host.txt").decode())

    def test_show_prints_to_stdout(self):
        code, out, _ = self._run("logs", "show", "--log-dir", str(self.dir))
        self.assertEqual(0, code)
        self.assertIn("Payroll.xlsx", out)

    def test_bad_timeframe_is_a_clean_error_not_a_traceback(self):
        code, _, err = self._run("logs", "show", "--since", "yesterday",
                                 "--log-dir", str(self.dir))
        self.assertEqual(2, code)
        self.assertIn("Unrecognised timeframe", err)

    def test_non_positive_lines_is_rejected(self):
        """`recent_text` slices lines[-n:], so 0 would print the WHOLE file under
        a 'last 0 lines' header and -1 would silently drop the first line."""
        for bad in ("0", "-1"):
            with self.assertRaises(SystemExit) as cm:
                with redirect_stderr(io.StringIO()):
                    polyctl.build_parser().parse_args(
                        ["logs", "show", "--lines", bad, "--log-dir", str(self.dir)])
            self.assertEqual(2, cm.exception.code)

    def test_positive_lines_is_accepted(self):
        args = polyctl.build_parser().parse_args(
            ["logs", "show", "--lines", "10", "--log-dir", str(self.dir)])
        self.assertEqual(10, args.lines)

    def test_paths_survives_a_file_vanishing_after_discovery(self):
        """discover() sees the file; a rotation can move it before stat().

        Patching Path.stat directly is no good here — Path.exists() is built on
        stat, so discovery itself would stop seeing the file. Returning an
        already-gone path from discover() is the real race: listed, then moved.
        """
        from polyhost.services import log_bundle
        gone = self.dir / "host_log.txt.7"          # never created
        with mock.patch.object(log_bundle, "discover",
                               return_value={"host": [self.dir / "host_log.txt", gone]}):
            code, out, _ = self._run("logs", "paths", "--log-dir", str(self.dir))
        self.assertEqual(0, code)
        self.assertIn("size unavailable", out)
        self.assertIn("host_log.txt", out)          # the surviving file still listed

    def test_missing_logs_reports_and_fails(self):
        empty = self.dir / "nope"
        empty.mkdir()
        code, _, err = self._run("logs", "bundle", "--log-dir", str(empty),
                                 "-o", str(self.dir / "x.zip"))
        self.assertEqual(1, code)
        self.assertIn("No PolyHost log files", err)

    def test_a_device_command_still_fails_without_a_host(self):
        """The offline path must be scoped to `logs` only — everything else
        still needs the socket and must say so."""
        code, _, err = self._run("status")
        self.assertEqual(1, code)
        self.assertIn("cannot reach PolyKybdHost", err)

    def test_clear_works_without_a_running_host(self):
        # Same reasoning as the rest of `logs`: tidying up after a mess is
        # exactly when the daemon is not there to ask.
        code, out, _ = self._run("logs", "clear", "--yes", "--log-dir", str(self.dir))
        self.assertEqual(code, 0)
        self.assertIn("cleared", out)
        self.assertEqual((self.dir / "host_log.txt").stat().st_size, 0)

    def test_clear_refuses_without_confirmation(self):
        # stdin is not a terminal under the test runner, so input() raises
        # EOFError — which must read as "no", never as consent.
        with mock.patch("builtins.input", side_effect=EOFError):
            code, out, _ = self._run("logs", "clear", "--log-dir", str(self.dir))
        self.assertEqual(code, 1)
        self.assertIn("cancelled", out)
        self.assertGreater((self.dir / "host_log.txt").stat().st_size, 0)

    def test_clear_refuses_on_anything_other_than_yes(self):
        for reply in ("", "n", "no", "maybe", "Y E S"):
            with mock.patch("builtins.input", return_value=reply):
                code, _, _ = self._run("logs", "clear", "--log-dir", str(self.dir))
            self.assertEqual(code, 1, f"reply {reply!r} should not have cleared")
            self.assertGreater((self.dir / "host_log.txt").stat().st_size, 0)

    def test_clear_accepts_a_typed_yes(self):
        with mock.patch("builtins.input", return_value="y"):
            code, _, _ = self._run("logs", "clear", "--log-dir", str(self.dir))
        self.assertEqual(code, 0)
        self.assertEqual((self.dir / "host_log.txt").stat().st_size, 0)

    def test_clear_honours_log_dir_rather_than_the_default(self):
        # --log-dir was missing from `clear`'s parser at first; the mocked
        # service tests could not see it because they pass the directory in.
        code, _, _ = self._run("logs", "clear", "--yes", "--log-dir", str(self.dir))
        self.assertEqual(code, 0)


class PolyctlLogsWithHostTest(unittest.TestCase):
    """When a host IS reachable, the bundle picks up its status as diagnostics."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.dir / "host_log.txt").write_text(
            _line(datetime.now(), "hello") + "\n", encoding="utf-8")

    def test_status_is_embedded_in_diagnostics(self):
        client = mock.Mock()
        client.call.return_value = {"connected": True, "fw_version": "0.13.1"}
        dest = self.dir / "b.zip"
        with mock.patch.object(polyctl, "connect", return_value=client):
            with redirect_stdout(io.StringIO()):
                code = polyctl.main(["logs", "bundle", "--log-dir", str(self.dir),
                                     "-o", str(dest)])
        self.assertEqual(0, code)
        with zipfile.ZipFile(dest) as zf:
            diag = zf.read("diagnostics.txt").decode()
        self.assertIn("0.13.1", diag)
        client.close.assert_called_once()

    def test_a_failing_status_call_still_produces_a_bundle(self):
        """Diagnostics are a bonus; an RPC error must not cost the user the logs."""
        client = mock.Mock()
        client.call.side_effect = polyctl.RpcError(-1, "device busy")
        dest = self.dir / "b.zip"
        with mock.patch.object(polyctl, "connect", return_value=client):
            with redirect_stdout(io.StringIO()):
                code = polyctl.main(["logs", "bundle", "--log-dir", str(self.dir),
                                     "-o", str(dest)])
        self.assertEqual(0, code)
        self.assertTrue(dest.exists())


if __name__ == "__main__":
    unittest.main()
