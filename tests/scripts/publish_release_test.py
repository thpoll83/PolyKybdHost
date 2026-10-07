"""`publish_release.py`'s release-safety guards.

The script decides whether publishing would ship a build that is not the
version on the label. Every guard in it answers that from a GitHub lookup, and
each one has already been got wrong in the same way: a FAILED lookup read as a
usable answer, so the guard passed instead of refusing.

- `release_exists()` folded 401/5xx/DNS into "no release", so an unannounced
  release looked like a clean pass.
- `tag_commit()` folded them into "no tag" -- and the caller SKIPS its check
  when there is no tag, so a 5xx let a publish through at whatever commit the
  tag really pointed at.

Both were found in review rather than by a test, which is what this file is
for. ⚠️ The contract under test is three-valued and the three are NOT
interchangeable: a value means "this is so", `""` means "confirmed absent",
and `None` means "could not tell" and must never be treated as either.

⚠️ `scripts/` is not a package, so the module is loaded by path.
"""
import importlib.util
import io
import contextlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "publish_release.py"


def load():
    """A fresh module per test: the tests replace its module-level helpers."""
    spec = importlib.util.spec_from_file_location("publish_release_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class VersionTupleTest(unittest.TestCase):
    def test_orders_numerically_not_lexically(self):
        m = load()
        # ⚠️ A string compare puts 0.10.0 BEFORE 0.9.20, which would hand the
        # Latest badge to the older release.
        self.assertLess(m.version_tuple("0.9.20"), m.version_tuple("0.10.0"))
        self.assertLess(m.version_tuple("0.9.3"), m.version_tuple("0.9.20"))


class TagCommitTest(unittest.TestCase):
    """The three outcomes, which the caller's guard depends on telling apart."""

    def _with_lookup(self, *responses):
        m = load()
        calls = list(responses)
        m._get_json = lambda *a, **k: calls.pop(0) if calls else (None, None)
        return m

    def test_sha_for_a_lightweight_tag(self):
        sha = "a" * 40
        m = self._with_lookup((200, {"object": {"type": "commit", "sha": sha}}))
        self.assertEqual(m.tag_commit("o", "r", "t", None), sha)

    def test_dereferences_an_annotated_tag(self):
        m = self._with_lookup(
            (200, {"object": {"type": "tag", "sha": "t" * 40}}),
            (200, {"object": {"sha": "c" * 40}}),
        )
        self.assertEqual(m.tag_commit("o", "r", "t", None), "c" * 40)

    def test_confirmed_404_is_absent_not_unknown(self):
        m = self._with_lookup((404, None))
        self.assertEqual(m.tag_commit("o", "r", "t", None), "")

    def test_every_other_failure_is_unknown(self):
        # ⚠️ None of these may read as "no tag": the caller skips its guard on
        # absent, and a skipped guard is how the wrong commit gets built.
        for status in (401, 403, 500, 502, None):
            with self.subTest(status=status):
                m = self._with_lookup((status, None))
                self.assertIsNone(m.tag_commit("o", "r", "t", None))

    def test_failed_annotated_dereference_is_unknown(self):
        m = self._with_lookup(
            (200, {"object": {"type": "tag", "sha": "t" * 40}}),
            (500, None),
        )
        self.assertIsNone(m.tag_commit("o", "r", "t", None))

    def test_unrecognised_ref_shape_is_unknown(self):
        m = self._with_lookup((200, {"object": {"type": "blob", "sha": "b" * 40}}))
        self.assertIsNone(m.tag_commit("o", "r", "t", None))


class ReleaseExistsTest(unittest.TestCase):
    """Same contract, the sibling that was fixed first."""

    def _with_urlopen(self, exc=None, status=200):
        m = load()
        if exc is not None:
            m.urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(exc)
        else:
            class _Resp:
                def __init__(self, s): self.status = s
                def __enter__(self): return self
                def __exit__(self, *a): return False
            m.urllib.request.urlopen = lambda *a, **k: _Resp(status)
        return m

    def test_200_is_true(self):
        self.assertIs(self._with_urlopen(status=200).release_exists("o", "r", "t", None), True)

    def test_404_is_false(self):
        import urllib.error
        m = self._with_urlopen(urllib.error.HTTPError("u", 404, "nf", None, None))
        self.assertIs(m.release_exists("o", "r", "t", None), False)

    def test_other_errors_are_unknown(self):
        import urllib.error
        for exc in (urllib.error.HTTPError("u", 500, "err", None, None),
                    urllib.error.HTTPError("u", 403, "forbidden", None, None),
                    TimeoutError("stalled"),
                    OSError("network down")):
            with self.subTest(exc=type(exc).__name__):
                m = self._with_urlopen(exc)
                self.assertIsNone(m.release_exists("o", "r", "t", None))


class ApiTimeoutTest(unittest.TestCase):
    def test_every_urlopen_passes_a_finite_timeout(self):
        """⚠️ urllib's default is the socket default, which is None -- block
        forever. A stalled lookup would then reach neither the value nor the
        None path, defeating the three-valued contract above."""
        m = load()
        self.assertIsInstance(m.API_TIMEOUT, (int, float))
        self.assertGreater(m.API_TIMEOUT, 0)
        seen = []
        for fn, args in ((m.release_exists, ("o", "r", "t", None)),
                         (m._get_json, ("o", "r", "/p", None))):
            m.urllib.request.urlopen = lambda *a, **k: seen.append(k.get("timeout")) or (
                (_ for _ in ()).throw(OSError("stop here")))
            fn(*args)
        self.assertEqual(seen, [m.API_TIMEOUT, m.API_TIMEOUT])

    def test_source_has_no_bare_urlopen(self):
        """A grep, because a new call site is the realistic regression."""
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("urlopen(req)", text)
        self.assertEqual(text.count("timeout=API_TIMEOUT"), text.count("urlopen(req"))


class GuardRefusesTest(unittest.TestCase):
    """`main()` must stop before publishing when the tag cannot be checked."""

    def _run(self, tag_result, target, tree_version, tag="v1.2.3"):
        m = load()
        m.repo_root = lambda: str(REPO_ROOT)
        m.detect = lambda root: ("host", "polyhost/_version.py", "main", "v")
        m.run = lambda cmd: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        m.prepared_tags = lambda prefix: [((1, 2, 3), tag)]
        m.show = lambda ref: ("# notes\nbody" if ref.endswith(".md")
                              else f"__major__ = {tree_version[0]}\n"
                                   f"__minor__ = {tree_version[1]}\n"
                                   f"__patch__ = {tree_version[2]}\n")
        m.owner_repo = lambda root: ("o", "r")
        m.get_token = lambda: None
        m.release_exists = lambda *a: False          # creating, so guards apply
        m.published_latest_version = lambda *a: ""
        m.commit_for_version = lambda *a: target
        m.tag_commit = lambda *a: tag_result
        sys.argv = ["publish_release.py", "--dry-run", "--tag", tag]
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                m.main()
        except SystemExit as e:
            if isinstance(e.code, str):
                return e.code
        return None

    def test_refuses_when_the_tag_cannot_be_checked(self):
        refusal = self._run(None, "d" * 40, (1, 2, 3))
        self.assertIsNotNone(refusal, "an unknown tag lookup must refuse, not publish")
        self.assertIn("cannot tell whether the tag", refusal)

    def test_refuses_when_the_tag_points_elsewhere(self):
        refusal = self._run("e" * 40, "d" * 40, (1, 2, 3))
        self.assertIsNotNone(refusal)
        self.assertIn("already exists, at", refusal)

    def test_proceeds_when_the_tag_is_confirmed_absent(self):
        self.assertIsNone(self._run("", "d" * 40, (1, 2, 3)))

    def test_proceeds_when_the_tag_matches_the_pin(self):
        self.assertIsNone(self._run("d" * 40, "d" * 40, (1, 2, 3)))


if __name__ == "__main__":
    unittest.main()
