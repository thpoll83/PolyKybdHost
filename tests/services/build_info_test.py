"""Build identity: a release the updater installed, or a git checkout."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
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
        (self.root / "a.txt").write_text("a\n")
        _git(self.root, "add", "a.txt")
        _git(self.root, "commit", "-q", "-m", "c", when=when)

    def _marker(self, version="1.16.0", installed="2026-10-09T06:00:00+00:00"):
        (self.root / build_info.MARKER_NAME).write_text(json.dumps({
            "tag": "v" + version, "version": version,
            "published_at": "2026-10-08T20:00:00Z", "installed_at": installed}))

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
        (self.root / "a.txt").write_text("changed\n")
        self.assertRegex(build_info.describe(self.root, "1.16.0"), r"@[0-9a-f]{10}\* ")

    @unittest.skipUnless(_HAS_GIT, "git not installed")
    def test_the_marker_wins_over_the_stale_git_head_the_updater_left(self):
        self._checkout()                       # committed 2026-10-08
        self._marker()                         # update applied 2026-10-09
        text = build_info.describe(self.root, "1.16.0")
        self.assertTrue(text.startswith(
            "release v1.16.0, published 2026-10-08, installed by update 2026-10-09"), text)
        self.assertIn("predates the files", text)

    @unittest.skipUnless(_HAS_GIT, "git not installed")
    def test_a_git_pull_after_the_update_makes_git_the_source_again(self):
        self._checkout(when="2026-10-10T10:00:00+00:00")   # newer than the update
        self._marker()
        self.assertTrue(build_info.describe(self.root, "1.16.0").startswith("git "))

    def test_a_marker_for_another_version_is_ignored(self):
        self._marker(version="1.15.0")
        self.assertIn("unknown source", build_info.describe(self.root, "1.16.0"))

    def test_the_marker_alone_names_the_release(self):
        build_info.write_release_marker(self.root, "v1.16.0", "1.16.0",
                                        "2026-10-08T20:00:00Z", "Release 1.16.0")
        self.assertTrue(build_info.describe(self.root, "1.16.0").startswith(
            "release v1.16.0, published 2026-10-08, installed by update "))

    def test_a_corrupt_marker_is_ignored(self):
        (self.root / build_info.MARKER_NAME).write_text("{not json")
        self.assertIn("unknown source", build_info.describe(self.root, "1.16.0"))

    def test_banner_has_the_firmware_shape(self):
        self.assertRegex(build_info.banner(self.root),
                         r"^== PolyKybdHost \d+\.\d+\.\d+ P\d+ \| build .+ ==$")


if __name__ == "__main__":
    unittest.main()
