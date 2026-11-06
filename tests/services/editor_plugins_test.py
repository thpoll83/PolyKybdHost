"""editor_plugins: copying the Vim/Neovim plugin and the Emacs package.

Every test works in a temporary home with fake plugin sources, so nothing
touches the real ~/.vim or init file. One test runs the real Vim when it is
installed, to check the generated help tags against :helptags.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from polyhost.services import editor_plugins as ep

ALL = ("vim", "gvim", "nvim", "emacs")


def which_of(*names):
    return lambda n: f"/usr/bin/{n}" if n in names else None


class Fixture(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.vim_src = self.tmp / "vim-plugin"
        for rel, text in {"plugin/polykybd.vim": "\" plugin v1\n",
                          "lua/polykybd.lua": "-- lua v1\n",
                          "doc/polykybd.txt": "*polykybd.txt*  x\n\n*polykybd* *g:polykybd_port*\n",
                          "README.md": "not copied\n"}.items():
            (self.vim_src / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.vim_src / rel).write_text(text)
        self.emacs_src = self.tmp / "emacs-package"
        self.emacs_src.mkdir()
        (self.emacs_src / "polykybd.el").write_text(";; polykybd v1\n(provide 'polykybd)\n")

    def kw(self, which=None):
        return dict(home=self.home, env={}, which=which or which_of(*ALL), system="Linux",
                    vim_source=self.vim_src, emacs_source=self.emacs_src)

    def status(self, editor, which=None):
        return ep.status([editor], **self.kw(which))[0]

    @property
    def vim_dir(self):
        return self.home / ".vim/pack/polykybd/start/polykybd"

    @property
    def init(self):
        return self.home / ".emacs.d/init.el"


class TestWhere(Fixture):

    def test_vim_and_neovim_folders(self):
        self.assertEqual(ep.vim_dir(ep.VIM, home="/h", env={}, system="Linux"),
                         Path("/h/.vim/pack/polykybd/start/polykybd"))
        self.assertEqual(ep.vim_dir(ep.VIM, home="/h", env={}, system="Windows"),
                         Path("/h/vimfiles/pack/polykybd/start/polykybd"))
        self.assertEqual(ep.vim_dir(ep.NEOVIM, home="/h", env={}, system="Linux"),
                         Path("/h/.local/share/nvim/site/pack/polykybd/start/polykybd"))
        self.assertEqual(ep.vim_dir(ep.NEOVIM, home="/h", env={"XDG_DATA_HOME": "/d"}, system="Linux"),
                         Path("/d/nvim/site/pack/polykybd/start/polykybd"))
        self.assertEqual(ep.vim_dir(ep.NEOVIM, home="/h", env={"LOCALAPPDATA": "/l"}, system="Windows"),
                         Path("/l/nvim-data/site/pack/polykybd/start/polykybd"))

    def test_emacs_reads_the_first_init_file_that_exists(self):
        self.assertEqual(ep.emacs_init_file(self.home, {}, "Linux"), self.init)
        (self.home / ".config/emacs").mkdir(parents=True)
        self.assertEqual(ep.emacs_init_file(self.home, {}, "Linux"),
                         self.home / ".config/emacs/init.el")
        (self.home / ".emacs.d").mkdir()
        self.assertEqual(ep.emacs_init_file(self.home, {}, "Linux"), self.init)
        (self.home / ".emacs").write_text("")
        self.assertEqual(ep.emacs_init_file(self.home, {}, "Linux"), self.home / ".emacs")
        self.assertEqual(ep.emacs_lisp_dir(self.home / ".emacs"), self.home / ".emacs.d/polykybd")


class TestVim(Fixture):

    def test_install_copies_the_plugin_folders_and_a_stamp(self):
        st = self.status(ep.VIM)
        self.assertEqual(st.state, ep.STATE_NOT_INSTALLED)
        [r] = ep.install([ep.VIM], **self.kw())
        self.assertTrue(r.ok and r.changed, r)
        self.assertEqual((self.vim_dir / "plugin/polykybd.vim").read_text(), "\" plugin v1\n")
        self.assertTrue((self.vim_dir / "lua/polykybd.lua").is_file())
        self.assertFalse((self.vim_dir / "README.md").exists())
        self.assertIn("polykybd\tpolykybd.txt\t/*polykybd*",
                      (self.vim_dir / "doc/tags").read_text())
        self.assertEqual(self.status(ep.VIM).state, ep.STATE_INSTALLED)
        [again] = ep.install([ep.VIM], **self.kw())
        self.assertFalse(again.changed)

    def test_a_changed_source_reads_outdated_and_refresh_copies_it(self):
        ep.install([ep.VIM], **self.kw())
        (self.vim_src / "plugin/polykybd.vim").write_text("\" plugin v2\n")
        self.assertEqual(self.status(ep.VIM).state, ep.STATE_OUTDATED)
        self.assertEqual(ep.refresh_installed(**self.kw()), [ep.VIM])
        self.assertEqual((self.vim_dir / "plugin/polykybd.vim").read_text(), "\" plugin v2\n")
        self.assertEqual(self.status(ep.VIM).state, ep.STATE_INSTALLED)
        self.assertEqual(ep.refresh_installed(**self.kw()), [])

    def test_a_file_dropped_from_the_source_is_deleted_on_refresh(self):
        ep.install([ep.VIM], **self.kw())
        (self.vim_src / "lua/polykybd.lua").unlink()
        ep.refresh_installed(**self.kw())
        self.assertFalse((self.vim_dir / "lua/polykybd.lua").exists())

    def test_a_copy_changed_by_hand_is_left_alone(self):
        ep.install([ep.VIM], **self.kw())
        (self.vim_dir / "plugin/polykybd.vim").write_text("\" my edit\n")
        (self.vim_src / "plugin/polykybd.vim").write_text("\" plugin v2\n")
        self.assertEqual(self.status(ep.VIM).state, ep.STATE_MODIFIED)
        self.assertEqual(ep.refresh_installed(**self.kw()), [])
        [r] = ep.install([ep.VIM], **self.kw())
        self.assertFalse(r.ok)
        [r] = ep.remove([ep.VIM], **self.kw())
        self.assertFalse(r.ok)
        self.assertEqual((self.vim_dir / "plugin/polykybd.vim").read_text(), "\" my edit\n")

    def test_a_hand_copy_in_the_same_folder_is_set_aside(self):
        (self.vim_dir / "plugin").mkdir(parents=True)
        (self.vim_dir / "plugin/polykybd.vim").write_text("\" old hand copy\n")
        st = self.status(ep.VIM)
        self.assertEqual(st.state, ep.STATE_MANUAL)
        self.assertFalse(ep.default_selection(st))
        [r] = ep.install([ep.VIM], **self.kw())
        self.assertTrue(r.ok and r.changed)
        self.assertEqual(r.backup.parent, self.home / ".vim/pack/polykybd")
        self.assertEqual((r.backup / "plugin/polykybd.vim").read_text(), "\" old hand copy\n")
        self.assertEqual(self.status(ep.VIM).state, ep.STATE_INSTALLED)

    def test_a_plugin_manager_copy_reads_manual(self):
        other = self.home / ".vim/plugged/polykybd/plugin"
        other.mkdir(parents=True)
        (other / "polykybd.vim").write_text("")
        st = self.status(ep.VIM)
        self.assertEqual(st.state, ep.STATE_MANUAL)
        self.assertEqual(Path(st.detail), other.parent)

    def test_remove_deletes_the_copy_and_the_empty_package_folders(self):
        ep.install([ep.VIM], **self.kw())
        [r] = ep.remove([ep.VIM], **self.kw())
        self.assertTrue(r.ok and r.changed)
        self.assertFalse((self.home / ".vim/pack/polykybd").exists())
        self.assertTrue((self.home / ".vim/pack").is_dir())

    def test_remove_keeps_a_file_the_user_added(self):
        ep.install([ep.VIM], **self.kw())
        (self.vim_dir / "after.vim").write_text("mine")
        ep.remove([ep.VIM], **self.kw())
        self.assertEqual((self.vim_dir / "after.vim").read_text(), "mine")
        self.assertFalse((self.vim_dir / "plugin").exists())

    def test_an_editor_that_is_not_installed(self):
        st = self.status(ep.NEOVIM, which=which_of("vim"))
        self.assertEqual(st.state, ep.STATE_NOT_PRESENT)
        self.assertEqual(ep.install(None, **self.kw(which_of("vim")))[0].editor, ep.VIM)

    def test_no_plugin_files_in_this_installation(self):
        shutil.rmtree(self.vim_src)
        st = self.status(ep.VIM)
        self.assertEqual(st.state, ep.STATE_NO_SOURCE)
        [r] = ep.install([ep.VIM], statuses=[st], **self.kw())
        self.assertFalse(r.ok)


class TestEmacs(Fixture):

    def test_install_creates_the_init_file_and_the_copy(self):
        [r] = ep.install([ep.EMACS], **self.kw())
        self.assertTrue(r.ok and r.changed, r)
        self.assertIsNone(r.backup)
        text = self.init.read_text()
        lisp = (self.home / ".emacs.d/polykybd").as_posix()
        self.assertIn(f'(add-to-list \'load-path "{lisp}")', text)
        self.assertIn("(polykybd-mode 1)", text)
        self.assertTrue((self.home / ".emacs.d/polykybd/polykybd.el").is_file())
        self.assertEqual(self.status(ep.EMACS).state, ep.STATE_INSTALLED)

    def test_an_existing_init_file_keeps_its_bytes_and_gets_a_backup(self):
        self.init.parent.mkdir(parents=True)
        original = b";;; init.el -*- lexical-binding: t -*-\r\n(setq x \"\xc3\xa9\")"
        self.init.write_bytes(original)
        [r] = ep.install([ep.EMACS], **self.kw())
        self.assertEqual(r.backup.read_bytes(), original)
        data = self.init.read_bytes()
        self.assertTrue(data.startswith(original + b"\r\n" + ep.BEGIN_MARKER.encode()))
        self.assertIn(b"(polykybd-mode 1))\r\n", data)
        [r] = ep.remove([ep.EMACS], **self.kw())
        self.assertTrue(r.ok and r.changed)
        self.assertEqual(self.init.read_bytes(), original + b"\r\n")
        self.assertFalse((self.home / ".emacs.d/polykybd").exists())

    def test_a_package_loaded_by_hand_reads_manual(self):
        self.init.parent.mkdir(parents=True)
        self.init.write_text("(use-package polykybd :config (polykybd-mode 1))\n")
        self.assertEqual(self.status(ep.EMACS).state, ep.STATE_MANUAL)
        self.init.write_text(";; I might try polykybd later\n")
        self.assertEqual(self.status(ep.EMACS).state, ep.STATE_NOT_INSTALLED)

    def test_a_block_for_another_folder_reads_stale_and_install_replaces_it(self):
        self.init.parent.mkdir(parents=True)
        self.init.write_text(ep.init_block("/old/place"))
        st = self.status(ep.EMACS)
        self.assertEqual(st.state, ep.STATE_STALE)
        self.assertEqual(st.detail, "/old/place")
        ep.install([ep.EMACS], **self.kw())
        self.assertNotIn("/old/place", self.init.read_text())
        self.assertEqual(self.init.read_text().count(ep.BEGIN_MARKER), 1)

    def test_a_deleted_copy_reads_outdated_and_refresh_restores_it(self):
        ep.install([ep.EMACS], **self.kw())
        shutil.rmtree(self.home / ".emacs.d/polykybd")
        self.assertEqual(self.status(ep.EMACS).state, ep.STATE_OUTDATED)
        self.assertEqual(ep.refresh_installed(**self.kw()), [ep.EMACS])
        self.assertTrue((self.home / ".emacs.d/polykybd/polykybd.el").is_file())

    def test_a_start_marker_without_an_end_marker_is_refused(self):
        self.init.parent.mkdir(parents=True)
        self.init.write_text(ep.BEGIN_MARKER + "\n(foo)\n")
        [r] = ep.install([ep.EMACS], **self.kw())
        self.assertFalse(r.ok)
        self.assertEqual(self.init.read_text(), ep.BEGIN_MARKER + "\n(foo)\n")

    def test_a_path_with_a_quote_is_escaped_for_lisp(self):
        block = ep.init_block('/a "b"/polykybd')
        self.assertIn('"/a \\"b\\"/polykybd"', block)
        self.assertEqual(ep._block_dir(block), '/a "b"/polykybd')


class TestHelpTags(unittest.TestCase):

    def test_tags_are_sorted_and_slashes_escaped(self):
        tags = ep.help_tags("x.txt", "*b* *a/b* text *a*\nnot*tag* |link|\n").decode()
        self.assertEqual(tags, "a\tx.txt\t/*a*\na/b\tx.txt\t/*a\\/b*\nb\tx.txt\t/*b*\n")

    @unittest.skipUnless(shutil.which("vim"), "needs vim")
    def test_the_shipped_help_file_gives_what_helptags_writes(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        shutil.copy(ep.VIM_SOURCE / "doc/polykybd.txt", tmp / "polykybd.txt")
        subprocess.run(["vim", "-u", "NONE", "-i", "NONE", "-Es", f"+helptags {tmp}", "+q"],
                       stdin=subprocess.DEVNULL, timeout=30, check=False)
        files = ep.shipped_files(ep.VIM)
        self.assertEqual(files["doc/tags"], (tmp / "tags").read_bytes())


class TestSettings(unittest.TestCase):

    def test_only_a_changed_port_or_a_token_needs_settings(self):
        self.assertFalse(ep.needs_settings(50164, ""))
        self.assertFalse(ep.needs_settings(None, None))
        self.assertTrue(ep.needs_settings(50165, ""))
        self.assertTrue(ep.needs_settings(50164, "secret"))


class TestStamp(Fixture):

    def test_the_stamp_lists_every_written_file(self):
        ep.install([ep.VIM], **self.kw())
        stamp = json.loads((self.vim_dir / ep.STAMP_NAME).read_text())
        self.assertEqual(sorted(stamp["files"]),
                         ["doc/polykybd.txt", "doc/tags", "lua/polykybd.lua", "plugin/polykybd.vim"])


if __name__ == "__main__":
    unittest.main()
