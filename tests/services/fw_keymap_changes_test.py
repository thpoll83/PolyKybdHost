"""services/fw_keymap_changes.py: which keymap changes an update names."""
import unittest

from polyhost.services import fw_keymap_changes as mod


class KeymapChangesTest(unittest.TestCase):
    def test_an_update_across_the_migration_names_it(self):
        self.assertEqual(len(mod.keymap_changes("1.13.0", "1.13.1")), 1)
        self.assertEqual(len(mod.keymap_changes("1.12.9", "1.14.0")), 1)

    def test_a_board_that_had_it_gets_no_note(self):
        self.assertEqual(mod.keymap_changes("1.13.1", "1.13.5"), [])
        self.assertEqual(mod.keymap_changes("1.14.0", "1.15.0"), [])

    def test_an_update_below_the_migration_gets_no_note(self):
        self.assertEqual(mod.keymap_changes("1.12.0", "1.13.0"), [])

    def test_an_unknown_installed_version_names_it(self):
        self.assertEqual(len(mod.keymap_changes(None, "1.13.1")), 1)
        self.assertEqual(len(mod.keymap_changes("", "v1.13.1")), 1)

    def test_entries_are_in_version_order(self):
        versions = [mod.parse_version(v) for v, _ in mod.KEYMAP_CHANGES]
        self.assertEqual(versions, sorted(versions))


if __name__ == "__main__":
    unittest.main()
