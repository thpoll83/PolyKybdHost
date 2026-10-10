"""Opening Settings and pressing OK must not change any value.

A QSpinBox clamps whatever it is given to its range, and OK writes the
clamped value back. A 10_000 cap on every int editor turned
browser_report_port 50164 into 10000 on every OK, so the browser extension
lost the host without anyone editing the field.
"""
import os
import unittest


@unittest.skipUnless(os.environ.get("DISPLAY")
                     or os.environ.get("QT_QPA_PLATFORM") == "offscreen",
                     "building the dialog needs a display (xvfb-run)")
class SettingsRoundTripTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _round_trip(self, settings):
        from polyhost.gui.settings_dialog import SettingsDialog
        dlg = SettingsDialog()
        self.addCleanup(dlg.deleteLater)
        dlg.setup(settings, developer_mode=True)
        return dlg.get_updated_settings()

    def test_every_default_survives_ok_unchanged(self):
        from polyhost.settings import DEFAULT_SETTINGS
        self.assertEqual(self._round_trip(dict(DEFAULT_SETTINGS)), DEFAULT_SETTINGS)

    def test_a_port_above_ten_thousand_is_kept(self):
        self.assertEqual(self._round_trip({"browser_report_port": 50164}),
                         {"browser_report_port": 50164})

    def test_negative_and_large_numbers_are_kept(self):
        values = {"some_offset": -5, "some_scale": 2500.5, "neg_scale": -0.25}
        self.assertEqual(self._round_trip(dict(values)), values)

    def test_a_stored_value_is_never_an_end_of_its_range(self):
        from polyhost.gui.settings_dialog import create_editor
        for value in (-5, 50164, -0.25, 2500.5, 0.75, -2_000_000_000.5):
            with self.subTest(value=value):
                box = create_editor(value)
                self.addCleanup(box.deleteLater)
                self.assertLess(box.minimum(), value)
                self.assertGreater(box.maximum(), value)



@unittest.skipUnless(os.environ.get("DISPLAY")
                     or os.environ.get("QT_QPA_PLATFORM") == "offscreen",
                     "building the dialog needs a display (xvfb-run)")
class LanguageSettingTest(unittest.TestCase):
    """`ui_language`: a dropdown that SHOWS each language in its own name and
    STORES the code, so a translated or renamed label never reaches the file."""

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        from polyhost import i18n
        i18n.install(i18n.SOURCE_LANGUAGE)

    def _combo(self, key, value):
        from polyhost.gui.settings_dialog import create_editor
        combo = create_editor(value, key)
        self.addCleanup(combo.deleteLater)
        return combo

    def test_lists_automatic_then_every_language_by_its_own_name(self):
        from polyhost import i18n
        combo = self._combo("ui_language", "auto")
        data = [combo.itemData(i) for i in range(combo.count())]
        labels = [combo.itemText(i) for i in range(combo.count())]
        self.assertEqual(data, ["auto"] + [lang.code for lang in i18n.LANGUAGES])
        self.assertEqual(labels[1:], [lang.endonym for lang in i18n.LANGUAGES])
        self.assertTrue(labels[0].startswith("Automatic ("))

    def test_endonyms_stay_untranslated_in_another_language(self):
        from polyhost import i18n
        i18n.install("pseudo")
        combo = self._combo("ui_language", "ja")
        self.assertEqual(combo.currentText(), "日本語")
        self.assertIn("Deutsch", [combo.itemText(i) for i in range(combo.count())])

    def test_a_pinned_language_round_trips_as_its_code(self):
        from polyhost.gui.settings_dialog import SettingsDialog
        dlg = SettingsDialog()
        self.addCleanup(dlg.deleteLater)
        dlg.setup({"ui_language": "zh_TW", "ui_theme": "dark"})
        self.assertEqual(dlg.get_updated_settings(), {"ui_language": "zh_TW", "ui_theme": "dark"})

    def test_a_value_outside_the_list_is_kept(self):
        combo = self._combo("ui_language", "sv")
        self.assertEqual(combo.currentData(), "sv")

    def test_theme_labels_are_translated_and_values_are_not(self):
        from polyhost import i18n
        i18n.install("pseudo")
        combo = self._combo("ui_theme", "light")
        self.assertEqual(combo.currentData(), "light")
        self.assertNotEqual(combo.currentText(), "Light")

    def test_every_setting_and_group_has_a_label(self):
        """A key missing here is shown in English under every language."""
        from polyhost.settings import DEFAULT_SETTINGS
        from polyhost.gui.settings_dialog import GROUP_LABELS, SETTING_LABELS, split_key
        self.assertEqual(set(DEFAULT_SETTINGS) - set(SETTING_LABELS), set())
        groups = {split_key(k)[0] for k in DEFAULT_SETTINGS}
        self.assertEqual(groups - set(GROUP_LABELS), set())


class LanguageRestartDecisionTest(unittest.TestCase):

    def tearDown(self):
        from polyhost import i18n
        i18n.install(i18n.SOURCE_LANGUAGE)

    def _needs_restart(self, setting, os_langs, running):
        from unittest import mock
        from polyhost import i18n
        from polyhost.gui import i18n_qt
        i18n.install(running)
        with mock.patch.object(i18n_qt, "os_ui_languages", return_value=os_langs), \
                mock.patch.dict(os.environ, {}, clear=False) as env:
            env.pop(i18n.ENV_OVERRIDE, None)
            return i18n_qt.language_change_needs_restart(setting)

    def test_auto_to_the_language_already_shown_needs_nothing(self):
        self.assertFalse(self._needs_restart("de", ["de-DE"], "de"))
        self.assertFalse(self._needs_restart("auto", ["de-DE"], "de"))

    def test_a_different_language_needs_a_restart(self):
        self.assertTrue(self._needs_restart("ja", ["de-DE"], "de"))
        self.assertTrue(self._needs_restart("auto", ["fr-FR"], "de"))


if __name__ == "__main__":
    unittest.main()
