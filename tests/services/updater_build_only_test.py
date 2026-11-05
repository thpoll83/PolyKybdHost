"""The build-only paths: the updater's rule, the installers' sparse patterns,
and what git does with those patterns all name the same files."""
import io
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from polyhost.services import updater

REPO = Path(__file__).resolve().parents[2]

# Paths that exercise every branch of the rule.
SAMPLE_FILES = [
    "README.md",
    "setup.py",
    "polyhost/__init__.py",
    "polyhost/res/overlays/kicad.png",
    "polyhost/res/overlay-mapping.poly.yaml",
    "polyhost/res/overlay_sources/README.md",
    "polyhost/res/overlay_sources/brand_marks.py",
    "polyhost/res/overlay_sources/dune2/dune2.yaml",
    "polyhost/res/overlay_sources/dune2/icons/harvester.png",
    "polyhost/res/overlay_sources/dune2/SOURCES.md",
    "polyhost/res/overlay_sources/dune2/deep/nested.yaml",
    "polyhost/res/overlay_sources/kicad/gen_titles.py",
    "tests/__init__.py",
    "tests/services/updater_test.py",
    "tools/poly_console.py",
    "testdata.txt",
]


def kept_by_rule(paths):
    """The files a copytree walk with is_build_only keeps: the file and every
    folder above it must be kept."""
    kept = set()
    for rel in paths:
        parts = rel.split("/")
        dirs = ["/".join(parts[:i]) for i in range(1, len(parts))]
        if any(updater.is_build_only(d, True) for d in dirs):
            continue
        if not updater.is_build_only(rel):
            kept.add(rel)
    return kept


class TestIsBuildOnly(unittest.TestCase):

    def test_sample_paths(self):
        self.assertEqual(kept_by_rule(SAMPLE_FILES), {
            "README.md",
            "setup.py",
            "polyhost/__init__.py",
            "polyhost/res/overlays/kicad.png",
            "polyhost/res/overlay-mapping.poly.yaml",
            "polyhost/res/overlay_sources/dune2/dune2.yaml",
            "tools/poly_console.py",
            "testdata.txt",
        })

    def test_extraction_and_walk_agree(self):
        """Extraction filters each member alone; the walk prunes folders. A
        kept file under a pruned folder would differ between the two."""
        by_member = {p for p in SAMPLE_FILES if not updater.is_build_only(p)}
        self.assertEqual(by_member, kept_by_rule(SAMPLE_FILES))

    def test_every_game_assets_spec_in_the_mapping_is_kept(self):
        """The app reads these at runtime (services/game_assets)."""
        mapping = (REPO / "polyhost/res/overlay-mapping.poly.yaml").read_text(encoding="utf-8")
        specs = set(re.findall(r"^\s*game_assets:\s*(\S+)\s*$", mapping, re.M))
        self.assertTrue(specs)
        for spec in specs:
            rel = f"polyhost/res/overlay_sources/{spec}"
            self.assertFalse(updater.is_build_only(rel), rel)
            self.assertTrue((REPO / rel).is_file(), rel)


class TestSparsePatterns(unittest.TestCase):

    def test_installers_pass_the_same_patterns(self):
        for script in ("scripts/install.sh", "scripts/install.ps1"):
            text = (REPO / script).read_text(encoding="utf-8")
            block = text[text.index("--sparse"):text.index("sparse-checkout set")]
            found = re.findall(r"^\s*'([^']+)'", block, re.M)
            self.assertEqual(tuple(found), updater.SPARSE_PATTERNS, script)

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_git_keeps_what_the_rule_keeps(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            for rel in SAMPLE_FILES:
                (src / rel).parent.mkdir(parents=True, exist_ok=True)
                (src / rel).write_text("x\n", encoding="utf-8")

            def git(*args, cwd, stdin=None):
                return subprocess.run(
                    ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                     "-c", "protocol.file.allow=always", *args],
                    cwd=cwd, input=stdin, capture_output=True, text=True, check=True)

            git("init", "-q", cwd=src)
            git("add", "-A", cwd=src)
            git("commit", "-q", "-m", "x", cwd=src)
            clone = Path(td) / "clone"
            git("clone", "-q", "--sparse", src.as_uri(), str(clone), cwd=td)
            git("sparse-checkout", "set", "--no-cone", "--stdin", cwd=clone,
                stdin="\n".join(updater.SPARSE_PATTERNS) + "\n")
            on_disk = {p.relative_to(clone).as_posix() for p in clone.rglob("*")
                       if p.is_file() and ".git" not in p.relative_to(clone).parts}
        self.assertEqual(on_disk, kept_by_rule(SAMPLE_FILES))


class TestUpdaterSkipsBuildOnly(unittest.TestCase):

    def _tarball(self, path: Path, top: str):
        with tarfile.open(path, "w:gz") as tar:
            for rel in SAMPLE_FILES:
                info = tarfile.TarInfo(name=f"{top}/{rel}")
                info.size = 2
                tar.addfile(info, io.BytesIO(b"x\n"))

    def _files(self, root: Path):
        return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}

    def test_extraction_skips_build_only_members(self):
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "r.tar.gz"
            self._tarball(archive, "thpoll83-PolyKybdHost-abc")
            dest = Path(td) / "out"
            dest.mkdir()
            with tarfile.open(archive, "r:gz") as tar:
                updater._safe_extract(tar, dest)
            got = self._files(dest / "thpoll83-PolyKybdHost-abc")
        self.assertEqual(got, kept_by_rule(SAMPLE_FILES))

    def test_extraction_skips_on_python_before_3_12(self):
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "r.tar.gz"
            self._tarball(archive, "top")
            dest = Path(td) / "out"
            dest.mkdir()
            with mock.patch("polyhost.services.updater.sys") as fake_sys:
                fake_sys.version_info = (3, 11, 0)
                with tarfile.open(archive, "r:gz") as tar:
                    updater._safe_extract(tar, dest)
            got = self._files(dest / "top")
        self.assertEqual(got, kept_by_rule(SAMPLE_FILES))

    def test_apply_update_does_not_copy_build_only_files(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            for rel in SAMPLE_FILES:
                (src / rel).parent.mkdir(parents=True, exist_ok=True)
                (src / rel).write_text("x\n", encoding="utf-8")
            install = Path(td) / "install"
            install.mkdir()
            with mock.patch.object(updater, "_run_pip"):
                updater.apply_update(src, install)
            got = self._files(install)
        self.assertEqual(got, kept_by_rule(SAMPLE_FILES))


if __name__ == "__main__":
    unittest.main()
