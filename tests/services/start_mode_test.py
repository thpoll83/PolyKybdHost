"""services/start_mode.py: when a plain launch starts as a forwarder, and the switch."""
import os
import tempfile
import unittest
import unittest.mock as mock

from polyhost.services import start_mode as sm


class StripOptionsTest(unittest.TestCase):
    def test_no_forwarder_is_dropped_by_default(self):
        self.assertEqual(sm.strip_options(["--dev", "--no-forwarder"]), ["--dev"])

    def test_connect_is_kept_unless_asked(self):
        argv = ["--connect", "/tmp/x.sock", "--dev"]
        self.assertEqual(sm.strip_options(argv), argv)

    def test_connect_with_its_endpoint_is_dropped(self):
        self.assertEqual(sm.strip_options(["--connect", "/tmp/x.sock", "--dev"], connect=True),
                         ["--dev"])

    def test_connect_without_an_endpoint_keeps_the_next_option(self):
        self.assertEqual(sm.strip_options(["--connect", "--dev"], connect=True), ["--dev"])

    def test_connect_equals_form_is_dropped(self):
        self.assertEqual(sm.strip_options(["--connect=/tmp/x.sock", "--dev"], connect=True),
                         ["--dev"])

    def test_the_input_is_not_changed(self):
        argv = ["--no-forwarder", "--dev"]
        sm.strip_options(argv)
        self.assertEqual(argv, ["--no-forwarder", "--dev"])


class PrecedenceTest(unittest.TestCase):
    def test_the_setting_alone_makes_a_plain_launch_a_forwarder(self):
        self.assertTrue(sm.forwarder_from_setting(setting=True))

    def test_without_the_setting_a_plain_launch_is_not_a_forwarder(self):
        self.assertFalse(sm.forwarder_from_setting(setting=False))

    def test_an_option_that_names_a_forwarder_leaves_it_to_main_app(self):
        # --host, --host-file and --detect-host start a forwarder by themselves, so the
        # setting is not what decides: False, and main_app reads the options.
        for option in ({"host": "10.0.0.1"}, {"host_file": "/tmp/ip"},
                       {"detect_host": True}):
            with self.subTest(option):
                self.assertFalse(sm.forwarder_from_setting(setting=True, **option))

    def test_headless_and_connect_win_over_the_setting(self):
        # The tray starts its background daemon with --headless. If the setting could turn
        # that daemon into a forwarder, the keyboard would stop working.
        self.assertFalse(sm.forwarder_from_setting(setting=True, headless=True))
        self.assertFalse(sm.forwarder_from_setting(setting=True, connect=""))      # bare
        self.assertFalse(sm.forwarder_from_setting(setting=True, connect="/tmp/sock"))

    def test_an_absent_connect_option_does_not_count(self):
        self.assertTrue(sm.forwarder_from_setting(setting=True, connect=None))

    def test_no_forwarder_turns_the_setting_off_for_one_run(self):
        self.assertFalse(sm.forwarder_from_setting(setting=True, no_forwarder=True))


class _Settings:
    def __init__(self, saved=True):
        self.values = {"ui_theme": "dark"}
        self.saved = saved
        self.sources = []

    def get_all(self):
        return dict(self.values)

    def set_all(self, new, source=None):
        self.sources.append(source)
        if self.saved:
            self.values = dict(new)
        return self.saved


class SwitchTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.folder, True))
        patcher = mock.patch("polyhost.settings.settings_path",
                             return_value=os.path.join(self.folder, "settings.yaml"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_switching_on_writes_the_setting_keeps_the_rest_and_leaves_the_marker(self):
        settings = _Settings()
        self.assertTrue(sm.set_start_as_forwarder(settings, True, "test"))
        self.assertIs(settings.values[sm.SETTING], True)
        self.assertEqual(settings.values["ui_theme"], "dark")        # the full dict is kept
        self.assertEqual(settings.sources, ["test"])
        self.assertTrue(sm.take_pair_prompt())

    def test_the_marker_is_taken_once(self):
        sm.mark_pair_prompt()
        self.assertTrue(sm.take_pair_prompt())
        self.assertFalse(sm.take_pair_prompt())

    def test_switching_off_leaves_no_marker(self):
        settings = _Settings()
        self.assertTrue(sm.set_start_as_forwarder(settings, False, "test"))
        self.assertIs(settings.values[sm.SETTING], False)
        self.assertFalse(sm.take_pair_prompt())

    def test_a_setting_that_was_not_saved_is_reported_and_leaves_no_marker(self):
        settings = _Settings(saved=False)
        self.assertFalse(sm.set_start_as_forwarder(settings, True, "test"))
        self.assertFalse(sm.take_pair_prompt())

    def test_the_default_is_off(self):
        from polyhost.settings import DEFAULT_SETTINGS
        self.assertIs(DEFAULT_SETTINGS[sm.SETTING], False)


if __name__ == "__main__":
    unittest.main()
