import importlib.metadata
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from polyhost import _bootstrap


class TestMissingRequirements(unittest.TestCase):

    def _write(self, content):
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False, encoding="utf-8")
        tmp.write(content)
        tmp.flush()
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return tmp.name

    def test_empty_when_file_missing(self):
        self.assertEqual(_bootstrap.missing_requirements("/no/such/file"), [])

    def test_ignores_comments_blanks_and_options(self):
        path = self._write("# a comment\n\n-r other.txt\n-i https://example.com\n")
        self.assertEqual(_bootstrap.missing_requirements(path), [])

    def test_strips_version_specifiers_and_extras(self):
        path = self._write("requests>=2.0\nPyQt5==5.15\npackage[extra]<2\n")
        with mock.patch.object(_bootstrap.importlib.metadata, "distribution") as dist:
            dist.return_value = mock.Mock()
            self.assertEqual(_bootstrap.missing_requirements(path), [])
            called_with = [c.args[0] for c in dist.call_args_list]
        self.assertEqual(called_with, ["requests", "PyQt5", "package"])

    def test_returns_only_missing_packages(self):
        path = self._write("requests\nnope-this-pkg-does-not-exist\npackaging\n")

        def fake_distribution(name):
            if name == "nope-this-pkg-does-not-exist":
                raise importlib.metadata.PackageNotFoundError(name)
            return mock.Mock()

        with mock.patch.object(_bootstrap.importlib.metadata,
                               "distribution", side_effect=fake_distribution):
            self.assertEqual(
                _bootstrap.missing_requirements(path),
                ["nope-this-pkg-does-not-exist"],
            )


class TestBootstrapDependencies(unittest.TestCase):

    def test_skips_pip_when_nothing_missing(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "requirements.txt").write_text("")
            with mock.patch.object(_bootstrap.subprocess, "run") as run:
                _bootstrap.bootstrap_dependencies(td)
            run.assert_not_called()

    def test_runs_pip_when_packages_missing(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "requirements.txt").write_text("not-a-real-package-xyz\n")
            with mock.patch.object(_bootstrap.subprocess, "run") as run:
                run.return_value = mock.Mock(returncode=0)
                _bootstrap.bootstrap_dependencies(td)
            run.assert_called_once()
            cmd = run.call_args.args[0]
            self.assertIn("install", cmd)
            self.assertIn("-r", cmd)
            self.assertEqual(cmd[-1], str(Path(td) / "requirements.txt"))

    def test_swallows_subprocess_errors(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "requirements.txt").write_text("not-a-real-package-xyz\n")
            with mock.patch.object(_bootstrap.subprocess, "run",
                                   side_effect=OSError("pip gone")):
                _bootstrap.bootstrap_dependencies(td)


if __name__ == "__main__":
    unittest.main()
