"""editor_plugins: copying the IDA plugin (ida-plugin/) to <IDAUSR>/plugins/polykybd.

Works in a temporary home with fake plugin sources, like editor_plugins_test.
"""
import json
import unittest
from pathlib import Path

from polyhost.services import editor_plugins as ep
from tests.services.editor_plugins_test import ALL, Fixture, which_of

REPO = Path(__file__).resolve().parents[2]


class IdaFixture(Fixture):

    def setUp(self):
        super().setUp()
        self.ida_src = self.tmp / "ida-plugin"
        self.ida_src.mkdir()
        (self.ida_src / "polykybd_ida.py").write_text("# ida v1\n")
        (self.ida_src / "ida-plugin.json").write_text("{}\n")
        (self.ida_src / "README.md").write_text("not copied\n")

    def kw(self, which=None):
        return {**super().kw(which), "ida_source": self.ida_src}

    @property
    def ida_dir(self):
        return self.home / ".idapro/plugins/polykybd"


class TestIdaWhere(unittest.TestCase):

    def test_user_dir_per_os_and_idausr(self):
        self.assertEqual(ep.ida_plugin_dir(home="/h", env={}, system="Linux"),
                         Path("/h/.idapro/plugins/polykybd"))
        self.assertEqual(ep.ida_plugin_dir(home="/h", env={}, system="Darwin"),
                         Path("/h/.idapro/plugins/polykybd"))
        self.assertEqual(ep.ida_plugin_dir(home="/h", env={"APPDATA": "/a"}, system="Windows"),
                         Path("/a/Hex-Rays/IDA Pro/plugins/polykybd"))
        # IDAUSR may list several folders; IDA reads the first for user files.
        self.assertEqual(ep.ida_plugin_dir(home="/h", env={"IDAUSR": "/u1:/u2"}, system="Linux"),
                         Path("/u1/plugins/polykybd"))
        self.assertEqual(ep.ida_plugin_dir(home="/h", env={"IDAUSR": "C:/u1;C:/u2"},
                                           system="Windows"),
                         Path("C:/u1/plugins/polykybd"))


class TestIda(IdaFixture):

    def test_not_present_without_ida_or_its_user_dir(self):
        self.assertEqual(self.status(ep.IDA).state, ep.STATE_NOT_PRESENT)

    def test_the_user_dir_alone_counts_as_present(self):
        (self.home / ".idapro").mkdir()
        st = self.status(ep.IDA)
        self.assertEqual(st.state, ep.STATE_NOT_INSTALLED)
        self.assertEqual(st.target, self.ida_dir)
        self.assertTrue(ep.default_selection(st))

    def test_install_copies_both_files_and_remove_deletes_them(self):
        (self.home / ".idapro" / "plugins" / "other.py").parent.mkdir(parents=True)
        (self.home / ".idapro" / "plugins" / "other.py").write_text("# someone else's\n")
        [r] = ep.install([ep.IDA], **self.kw())
        self.assertTrue(r.ok and r.changed, r.message)
        self.assertEqual(sorted(p.name for p in self.ida_dir.iterdir()),
                         [ep.STAMP_NAME, "ida-plugin.json", "polykybd_ida.py"])
        self.assertEqual(self.status(ep.IDA).state, ep.STATE_INSTALLED)
        [r] = ep.remove([ep.IDA], **self.kw())
        self.assertTrue(r.ok and r.changed, r.message)
        self.assertFalse(self.ida_dir.exists())
        # The plugins folder and other plugins in it stay.
        self.assertTrue((self.home / ".idapro" / "plugins" / "other.py").is_file())

    def test_a_changed_source_reads_outdated_and_refresh_copies_it(self):
        (self.home / ".idapro").mkdir()
        ep.install([ep.IDA], **self.kw())
        (self.ida_src / "polykybd_ida.py").write_text("# ida v2\n")
        self.assertEqual(self.status(ep.IDA).state, ep.STATE_OUTDATED)
        kw = self.kw()
        kw.pop("ida_source")
        self.assertIn(ep.IDA, ep.refresh_installed(ida_source=self.ida_src, **kw))
        self.assertEqual((self.ida_dir / "polykybd_ida.py").read_text(), "# ida v2\n")

    def test_a_copy_changed_by_hand_is_left_alone(self):
        (self.home / ".idapro").mkdir()
        ep.install([ep.IDA], **self.kw())
        (self.ida_dir / "polykybd_ida.py").write_text("# edited\n")
        self.assertEqual(self.status(ep.IDA).state, ep.STATE_MODIFIED)
        [r] = ep.remove([ep.IDA], **self.kw())
        self.assertFalse(r.ok)
        self.assertTrue((self.ida_dir / "polykybd_ida.py").is_file())

    def test_a_folder_this_app_did_not_write_reads_manual(self):
        self.ida_dir.mkdir(parents=True)
        (self.ida_dir / "polykybd_ida.py").write_text("# by hand\n")
        self.assertEqual(self.status(ep.IDA).state, ep.STATE_MANUAL)

    def test_found_on_path(self):
        self.assertEqual(self.status(ep.IDA, which_of(*ALL, "ida")).state,
                         ep.STATE_NOT_INSTALLED)


class TestShippedIdaPlugin(unittest.TestCase):

    def test_the_shipped_files_are_found_and_the_metadata_names_the_entry_point(self):
        files = ep.shipped_files(ep.IDA)
        self.assertEqual(sorted(files), ["ida-plugin.json", "polykybd_ida.py"])
        meta = json.loads(files["ida-plugin.json"])
        self.assertEqual(meta["IDAMetadataDescriptorVersion"], 1)
        self.assertEqual(meta["plugin"]["entryPoint"], "polykybd_ida.py")
        for key in ("name", "version", "urls", "authors"):
            self.assertIn(key, meta["plugin"])


if __name__ == "__main__":
    unittest.main()
