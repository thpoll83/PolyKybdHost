"""scripts/run_tests.py checks requirements-test.txt before it runs the suite.

A fresh container without the test dependencies made dozens of tests ERROR as if
they were regressions, in every session. These tests pin the check: it follows
``-r`` includes, skips a line whose platform marker does not match, reports a
missing package and an unmet version, and never installs into a Python that is
not a venv.
"""
import importlib.util
import shutil
import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("run_tests", ROOT / "scripts" / "run_tests.py")
run_tests = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_tests)

OTHER_PLATFORM = "win32" if sys.platform != "win32" else "linux"


class RequirementCheckTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def write(self, name, text):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_includes_are_followed_and_comments_dropped(self):
        self.write("inner.txt", "pip  # the installer\n# a comment\n")
        outer = self.write("outer.txt", "-r inner.txt\nunittest-not-a-dist\n")
        self.assertEqual(run_tests.requirement_lines(outer), ["pip", "unittest-not-a-dist"])

    def test_pip_options_are_dropped_and_both_include_forms_followed(self):
        self.write("a.txt", "pip\n")
        self.write("b.txt", "setuptools\n")
        outer = self.write("outer.txt", "--index-url https://example.invalid/simple\n-c c.txt\n"
                                        "-e .\n-r a.txt\n--requirement=b.txt\n")
        self.assertEqual(run_tests.requirement_lines(outer), ["pip", "setuptools"])

    def test_a_line_that_is_no_plain_requirement_is_not_checked(self):
        path = self.write("r.txt", "git+https://example.invalid/x.git\n./dist/x-1.0-py3-none-any.whl\n"
                                   "no-such-package-polykybd\n")
        self.assertEqual(run_tests.missing_requirements(path), ["no-such-package-polykybd"])
        with mock.patch.dict(sys.modules, {"packaging.requirements": None}):
            self.assertEqual(run_tests.missing_requirements(path), ["no-such-package-polykybd"])

    def test_a_missing_package_is_reported_once(self):
        path = self.write("r.txt", "pip\nno-such-package-polykybd\nno-such-package-polykybd\n")
        self.assertEqual(run_tests.missing_requirements(path), ["no-such-package-polykybd"])

    def test_a_line_for_another_platform_is_skipped(self):
        path = self.write("r.txt", f'no-such-package-polykybd; sys_platform == "{OTHER_PLATFORM}"\n')
        self.assertEqual(run_tests.missing_requirements(path), [])

    def test_an_unmet_version_is_reported(self):
        path = self.write("r.txt", "pip>=9999\n")
        self.assertEqual(run_tests.missing_requirements(path), ["pip>=9999"])

    def test_it_never_installs_outside_a_venv(self):
        with mock.patch.object(run_tests, "missing_requirements", return_value=["x"]), \
                mock.patch.object(run_tests.sys, "prefix", run_tests.sys.base_prefix), \
                mock.patch.object(run_tests.subprocess, "run") as pip:
            self.assertFalse(run_tests.check_requirements(install=True))
        pip.assert_not_called()

    def test_in_a_venv_it_installs_and_checks_again(self):
        with mock.patch.object(run_tests, "missing_requirements", side_effect=[["x"], []]), \
                mock.patch.object(run_tests.sys, "prefix", "/some/venv"), \
                mock.patch.object(run_tests.subprocess, "run") as pip:
            pip.return_value.returncode = 0
            self.assertTrue(run_tests.check_requirements(install=True))
        args = pip.call_args[0][0]
        self.assertEqual(args[1:4], ["-m", "pip", "install"])
        self.assertEqual(Path(args[-1]), run_tests.TEST_REQUIREMENTS)


if __name__ == "__main__":
    unittest.main()
