"""The user's overlay sets (services/user_overlays.py): the store, the files the
real loader reads, and the mapping they are laid over."""
import os
import shutil
import tempfile
import unittest

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode, Modifier
from polyhost.services import overlay_preview
from polyhost.services import user_overlays as uo

BOX = [{"rect": [0, 0, 72, 40]}]


class StoreTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="polykybd-uo-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_save_list_load_remove(self):
        r = uo.save_set("Blender", [{"key": "F5", "drawing": BOX, "legend": False},
                                    {"key": "KC_A", "mods": ["ctrl"], "drawing": BOX}], self.root)
        self.assertEqual(r["placed"], [{"key": "KC_F5", "mods": [], "legend": False},
                                       {"key": "KC_A", "mods": ["CTRL"], "legend": True}])
        self.assertEqual(uo.list_sets(self.root), [{"app": "blender", "keys": 2}])
        self.assertEqual(len(uo.load_set("blender", self.root)["bindings"]), 2)
        self.assertTrue(uo.remove_set("blender", self.root))
        self.assertEqual(uo.list_sets(self.root), [])
        self.assertFalse(uo.remove_set("blender", self.root))

    def test_a_later_binding_for_the_same_key_replaces_the_earlier(self):
        uo.save_set("x", [{"key": "KC_Q", "drawing": BOX},
                          {"key": "KC_Q", "drawing": BOX, "legend": False}], self.root)
        bindings = uo.load_set("x", self.root)["bindings"]
        self.assertEqual(len(bindings), 1)
        self.assertFalse(bindings[0]["legend"])

    def test_an_empty_set_is_removed(self):
        uo.save_set("x", [{"key": "KC_Q", "drawing": BOX}], self.root)
        uo.save_set("x", [], self.root)
        self.assertIsNone(uo.load_set("x", self.root))

    def test_the_files_carry_each_image_and_the_no_legend_keys(self):
        uo.save_set("x", [{"key": "KC_F5", "drawing": BOX, "legend": False},
                          {"key": "KC_A", "mods": ["CTRL"], "drawing": BOX},
                          {"key": "KC_Q", "mods": ["GUI", "SHIFT"], "drawing": BOX}], self.root)
        files = uo.files_for("x", self.root)
        self.assertEqual([os.path.basename(f) for f in files],
                         ["user_x.mods.png", "user_x.extra.mods.png"])
        conv = ImageConverter(DeviceSettings())
        self.assertTrue(conv.open(files[0]))
        self.assertEqual(set(conv.no_legend), {(0, KeyCode.KC_F5.value)})
        self.assertEqual(set(conv.extract_overlays(Modifier.NO_MOD)), {KeyCode.KC_F5.value})
        self.assertEqual(set(conv.extract_overlays(Modifier.CTRL)), {KeyCode.KC_A.value})
        conv = ImageConverter(DeviceSettings())
        self.assertTrue(conv.open(files[1]))
        self.assertEqual(set(conv.extract_overlays(Modifier.GUI_SHIFT)), {KeyCode.KC_Q.value})

    def test_the_star_set(self):
        uo.save_set("*", [{"key": "KC_ESC", "drawing": BOX}], self.root)
        self.assertEqual([os.path.basename(f) for f in uo.star_files(self.root)],
                         ["user__all.mods.png"])
        self.assertEqual(uo.list_sets(self.root)[0]["app"], "*")

    def test_refusals(self):
        for app in ("../evil", "a/b", "a,b", "", "x" * 70, None, "C:\\x", ".hidden"):
            with self.assertRaises(uo.UserOverlayError, msg=repr(app)):
                uo.save_set(app, [{"key": "KC_Q", "drawing": BOX}], self.root)
        for b in ({"key": "MO(1)", "drawing": BOX}, {"key": "KC_NOPE", "drawing": BOX},
                  {"key": "KC_Q", "drawing": []}, {"key": "KC_Q", "drawing": BOX, "mods": ["HYPER"]},
                  {"key": "KC_Q", "drawing": BOX, "legend": "no"},
                  {"key": "KC_Q", "drawing": BOX, "path": "/etc/passwd"}, "KC_Q"):
            with self.assertRaises(uo.UserOverlayError, msg=repr(b)):
                uo.save_set("x", [b], self.root)
        self.assertEqual(os.listdir(self.root), [])

    def test_an_app_name_stays_inside_the_folder(self):
        uo.save_set("my tool.exe", [{"key": "KC_Q", "drawing": BOX}], self.root)
        for path in uo.files_for("my tool.exe", self.root):
            self.assertTrue(os.path.realpath(path).startswith(os.path.realpath(self.root)))


class MergeTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="polykybd-uo-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.shipped = {
            "chrome,google chrome": {
                "overlay": ["chrome.mods.png"],
                "urls-contains": {"miro.com": {"overlay": "miro.mods.png"}},
                "os": {"macos": {"overlay": ["chrome_mac.mods.png"]}},
            },
            "term": {"titles-contains": {"nano": {"overlay": ["nano.mods.png"]}}},
        }

    def test_a_user_set_is_laid_over_every_route_of_the_shipped_entry(self):
        uo.save_set("google chrome", [{"key": "KC_Q", "drawing": BOX}], self.root)
        mine = uo.files_for("google chrome", self.root)
        merged = uo.merged_mapping(self.shipped, self.root)
        entry = merged["chrome,google chrome"]
        self.assertEqual(entry["overlay"], ["chrome.mods.png"] + mine)
        self.assertEqual(entry["urls-contains"]["miro.com"]["overlay"], ["miro.mods.png"] + mine)
        self.assertEqual(entry["os"]["macos"]["overlay"], ["chrome_mac.mods.png"] + mine)
        # The shipped dict is unchanged.
        self.assertEqual(self.shipped["chrome,google chrome"]["overlay"], ["chrome.mods.png"])

    def test_an_entry_without_its_own_overlay_gets_one(self):
        uo.save_set("term", [{"key": "KC_Q", "drawing": BOX}], self.root)
        entry = uo.merged_mapping(self.shipped, self.root)["term"]
        self.assertEqual(entry["overlay"], uo.files_for("term", self.root))
        self.assertEqual(entry["titles-contains"]["nano"]["overlay"][0], "nano.mods.png")

    def test_a_new_app_gets_its_own_entry_and_the_star_set_none(self):
        uo.save_set("mytool", [{"key": "KC_Q", "drawing": BOX}], self.root)
        uo.save_set("*", [{"key": "KC_ESC", "drawing": BOX}], self.root)
        merged = uo.merged_mapping(self.shipped, self.root)
        self.assertEqual(merged["mytool"], {"overlay": uo.files_for("mytool", self.root)})
        self.assertNotIn("*", merged)

    def test_the_preview_finds_the_entry_by_one_of_its_names(self):
        self.assertEqual(overlay_preview.entry_key("google chrome", self.shipped),
                         "chrome,google chrome")
        self.assertIsNone(overlay_preview.entry_key("nothing", self.shipped))


if __name__ == "__main__":
    unittest.main()
