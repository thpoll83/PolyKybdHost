"""hook_install.status(): the state each row of Integrations > AI agents shows."""
import json
import os
import tempfile
import unittest

from polyhost.services.agents import hook_install as hi

ARGV = ["/opt/poly/polyctl"]
OTHER = ["/old/place/polyctl"]


class HookStatusTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def _write(self, rel, text):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def _status(self, vendor, argv=ARGV):
        return hi.status(vendor, self.home, argv)

    def test_every_vendor_has_a_config_path_the_planner_writes(self):
        for vendor in hi.VENDORS:
            with self.subTest(vendor=vendor):
                changes = hi.plan(vendor, self.home, argv=ARGV)
                self.assertEqual([c.path for c in changes], [hi.config_path(vendor, self.home)])

    def test_no_file_is_not_installed_and_has_nothing_to_remove(self):
        for vendor in hi.VENDORS:
            with self.subTest(vendor=vendor):
                st = self._status(vendor)
                self.assertEqual(st.state, hi.STATE_NOT_INSTALLED)
                self.assertFalse(st.has_ours)
                self.assertFalse(os.path.exists(st.path))   # status writes nothing

    def test_after_install_every_vendor_is_installed(self):
        for vendor in hi.VENDORS:
            with self.subTest(vendor=vendor):
                hi.apply(hi.plan(vendor, self.home, argv=ARGV))
                st = self._status(vendor)
                self.assertEqual(st.state, hi.STATE_INSTALLED)
                self.assertTrue(st.has_ours)

    def test_hooks_of_another_path_are_outdated(self):
        for vendor in hi.VENDORS:
            with self.subTest(vendor=vendor):
                hi.apply(hi.plan(vendor, self.home, argv=OTHER))
                self.assertEqual(self._status(vendor).state, hi.STATE_OUTDATED)

    def test_the_users_own_hooks_alone_are_not_installed(self):
        self._write(".claude/settings.json", json.dumps(
            {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "my-linter"}]}]}}))
        self.assertEqual(self._status("claude-code").state, hi.STATE_NOT_INSTALLED)

    def test_a_codex_notify_of_the_users_own_is_a_conflict(self):
        self._write(".codex/config.toml", 'notify = ["my-notifier"]\n')
        st = self._status("codex")
        self.assertEqual(st.state, hi.STATE_CONFLICT)
        self.assertIn("notify", st.detail)
        self.assertFalse(st.has_ours)

    def test_valid_json_of_another_shape_is_that_agents_error(self):
        """{"hooks": null} made plan_claude() raise TypeError, and the page's
        status scan then showed no row for any agent."""
        self._write(".claude/settings.json", '{"hooks": null}')
        self._write(".gemini/settings.json", "[1, 2]")
        states = {v: self._status(v).state for v in hi.VENDORS}
        self.assertEqual(states["claude-code"], hi.STATE_ERROR)
        self.assertEqual(states["gemini"], hi.STATE_ERROR)
        self.assertEqual(states["codex"], hi.STATE_NOT_INSTALLED)    # the others still read

    def test_a_broken_settings_file_is_an_error_not_an_exception(self):
        self._write(".gemini/settings.json", "{ not json")
        st = self._status("gemini")
        self.assertEqual(st.state, hi.STATE_ERROR)
        self.assertTrue(st.detail)


if __name__ == "__main__":
    unittest.main()
