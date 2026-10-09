"""Build identity: a release the updater installed, or a git checkout."""
import os
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from polyhost.services import build_info

_HAS_GIT = shutil.which("git") is not None


def _git(root, *args, when="2026-10-08T10:00:00+00:00"):
    env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when,
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL=os.devnull)
    subprocess.run(["git", "-C", str(root), *args], check=True, env=env,
                   capture_output=True)


class BuildInfoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _checkout(self, branch="feature/x", when="2026-10-08T10:00:00+00:00"):
        _git(self.root, "init", "-q", "-b", branch)
        (self.root / "a.txt").write_text("a\n", encoding="utf-8")
        _git(self.root, "add", "a.txt")
        _git(self.root, "commit", "-q", "-m", "c", when=when)

    def _marker(self, version="1.16.0"):
        # The updater's own writer, so the marker records the HEAD it found.
        build_info.write_release_marker(self.root, "v" + version, version,
                                        "2026-10-08T20:00:00Z")

    def test_no_checkout_and_no_marker_says_unknown(self):
        self.assertIn("unknown source", build_info.describe(self.root, "1.16.0"))

    @unittest.skipUnless(_HAS_GIT, "git not installed")
    def test_a_clean_checkout_names_branch_hash_and_date(self):
        self._checkout()
        text = build_info.describe(self.root, "1.16.0")
        self.assertRegex(text, r"^git feature/x@[0-9a-f]{10} 2026-10-08$")

    @unittest.skipUnless(_HAS_GIT, "git not installed")
    def test_a_modified_tracked_file_marks_the_build_dirty(self):
        self._checkout()
        (self.root / "a.txt").write_text("changed\n", encoding="utf-8")
        self.assertRegex(build_info.describe(self.root, "1.16.0"), r"@[0-9a-f]{10}\* ")

    @unittest.skipUnless(_HAS_GIT, "git not installed")
    def test_the_marker_wins_over_the_stale_git_head_the_updater_left(self):
        self._checkout()
        self._marker()                         # the update, on top of that HEAD
        text = build_info.describe(self.root, "1.16.0")
        self.assertTrue(text.startswith(
            "release v1.16.0, published 2026-10-08, installed by update "), text)
        self.assertIn("predates the files", text)

    @unittest.skipUnless(_HAS_GIT, "git not installed")
    def test_a_new_commit_after_the_update_makes_git_the_source_again(self):
        self._checkout()
        self._marker()
        (self.root / "b.txt").write_text("b\n", encoding="utf-8")
        _git(self.root, "add", "b.txt")
        _git(self.root, "commit", "-q", "-m", "pulled")
        self.assertTrue(build_info.describe(self.root, "1.16.0").startswith("git "))

    @unittest.skipUnless(_HAS_GIT, "git not installed")
    def test_checking_out_an_OLDER_commit_after_the_update_makes_git_the_source(self):
        # A commit date older than the update must not hand the build back to
        # the marker: what counts is that HEAD moved (Greptile review).
        self._checkout(when="2026-10-01T10:00:00+00:00")
        _git(self.root, "branch", "old")
        (self.root / "b.txt").write_text("b\n", encoding="utf-8")
        _git(self.root, "add", "b.txt")
        _git(self.root, "commit", "-q", "-m", "newer")
        self._marker()
        _git(self.root, "checkout", "-q", "old")
        self.assertTrue(build_info.describe(self.root, "1.16.0").startswith("git old@"))

    def test_a_marker_for_another_version_is_ignored(self):
        self._marker(version="1.15.0")
        self.assertIn("unknown source", build_info.describe(self.root, "1.16.0"))

    def test_the_marker_alone_names_the_release(self):
        build_info.write_release_marker(self.root, "v1.16.0", "1.16.0",
                                        "2026-10-08T20:00:00Z", "Release 1.16.0")
        self.assertTrue(build_info.describe(self.root, "1.16.0").startswith(
            "release v1.16.0, published 2026-10-08, installed by update "))

    def test_a_corrupt_marker_is_ignored(self):
        (self.root / build_info.MARKER_NAME).write_text("{not json", encoding="utf-8")
        self.assertIn("unknown source", build_info.describe(self.root, "1.16.0"))

    @unittest.skipUnless(_HAS_GIT, "git not installed")
    def test_an_unreadable_HEAD_does_not_overrule_the_marker(self):
        self._checkout()
        self._marker()
        with unittest.mock.patch.object(build_info, "_git", return_value=None):
            text = build_info.describe(self.root, "1.16.0")
        self.assertTrue(text.startswith("release v1.16.0"), text)

    def test_the_startup_banner_fills_the_cache_the_dialog_reads(self):
        build_info._cached = None
        try:
            with unittest.mock.patch.object(build_info, "_describe",
                                            return_value="x") as work:
                build_info.banner()
                build_info.describe()
            work.assert_called_once()
        finally:
            build_info._cached = None

    def test_the_default_description_is_computed_once_per_process(self):
        build_info._cached = None
        try:
            first = build_info.describe()
            build_info._cached = "sentinel"
            self.assertEqual(build_info.describe(), "sentinel")
            self.assertTrue(first)
        finally:
            build_info._cached = None

    def test_banner_has_the_firmware_shape(self):
        self.assertRegex(build_info.banner(self.root),
                         r"^== PolyKybdHost \d+\.\d+\.\d+ P\d+ \| build .+ ==$")


if __name__ == "__main__":
    unittest.main()
