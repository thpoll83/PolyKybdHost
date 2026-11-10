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

    def test_every_setting_has_a_label(self):
        """A key missing here is shown in English under every language."""
        from polyhost.settings import DEFAULT_SETTINGS
        from polyhost.gui.settings_dialog import SETTING_LABELS
        self.assertEqual(set(DEFAULT_SETTINGS) - set(SETTING_LABELS), set())


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



class DescriptionTest(unittest.TestCase):
    """Every setting has a description, shown as its tooltip."""

    def test_every_default_setting_has_a_description(self):
        from polyhost.gui.settings_dialog import SETTING_DESCRIPTIONS
        from polyhost.settings import DEFAULT_SETTINGS
        self.assertEqual(set(DEFAULT_SETTINGS) - set(SETTING_DESCRIPTIONS), set())

    def test_no_description_for_a_setting_that_does_not_exist(self):
        from polyhost.gui.settings_dialog import SETTING_DESCRIPTIONS
        from polyhost.settings import DEFAULT_SETTINGS
        self.assertEqual(set(SETTING_DESCRIPTIONS) - set(DEFAULT_SETTINGS), set())

    def test_the_tooltip_is_escaped_rich_text(self):
        from unittest import mock
        from polyhost.gui import settings_dialog
        with mock.patch.dict(settings_dialog.SETTING_DESCRIPTIONS,
                             {"x_y": "a < b & c"}):
            self.assertEqual(settings_dialog.setting_tooltip("x_y"),
                             "<p>a &lt; b &amp; c</p>")
        self.assertEqual(settings_dialog.setting_tooltip("no_such_key"), "")


class DialogSizeTest(unittest.TestCase):
    """Half the screen, with the old 640x480 as the minimum."""

    def test_half_of_a_large_screen(self):
        from PyQt5.QtCore import QSize
        from polyhost.gui.settings_dialog import initial_dialog_size
        self.assertEqual(initial_dialog_size(QSize(2560, 1400)), QSize(1280, 700))

    def test_never_below_the_old_size(self):
        from PyQt5.QtCore import QSize
        from polyhost.gui.settings_dialog import initial_dialog_size
        self.assertEqual(initial_dialog_size(QSize(1024, 768)), QSize(640, 480))
        self.assertEqual(initial_dialog_size(QSize(1600, 800)), QSize(800, 480))


@unittest.skipUnless(os.environ.get("DISPLAY")
                     or os.environ.get("QT_QPA_PLATFORM") == "offscreen",
                     "building the dialog needs a display (xvfb-run)")
class BuiltDialogTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self):
        from polyhost.gui.settings_dialog import SettingsDialog
        from polyhost.settings import DEFAULT_SETTINGS
        dlg = SettingsDialog()
        self.addCleanup(dlg.deleteLater)
        dlg.setup(dict(DEFAULT_SETTINGS), developer_mode=True)
        return dlg

    def test_every_editor_and_its_label_carry_the_tooltip(self):
        from PyQt5.QtWidgets import QLabel
        from polyhost.gui.settings_dialog import setting_tooltip
        dlg = self._dialog()
        labels = {lbl.toolTip() for lbl in dlg.findChildren(QLabel)}
        for key, widget in dlg.edit_widgets.items():
            with self.subTest(key=key):
                self.assertEqual(widget.toolTip(), setting_tooltip(key))
                self.assertIn(setting_tooltip(key), labels)

    def test_opens_at_least_at_the_old_size(self):
        dlg = self._dialog()
        self.assertGreaterEqual(dlg.width(), 640)
        self.assertGreaterEqual(dlg.height(), 480)
        self.assertEqual((dlg.minimumWidth(), dlg.minimumHeight()), (640, 480))

    def test_no_push_button_besides_ok_and_cancel(self):
        """The glyph-script reset button is gone: the tray's Keycap Script menu
        has Standard as its first entry."""
        from PyQt5.QtWidgets import QDialogButtonBox, QPushButton
        dlg = self._dialog()
        box = dlg.findChild(QDialogButtonBox)
        extra = [b for b in dlg.findChildren(QPushButton) if b.parent() is not box]
        self.assertEqual(extra, [])

    def test_each_game_folder_row_has_a_browse_button(self):
        from unittest import mock
        from PyQt5.QtWidgets import QToolButton
        from polyhost.gui import settings_dialog as sd
        self.assertIn("game_d2k_data_dir", sd.FOLDER_KEYS)
        dlg = self._dialog()
        buttons = dlg.findChildren(QToolButton)
        self.assertEqual(len([b for b in buttons if b.text() == "…"]), len(sd.FOLDER_KEYS))
        edit = dlg.edit_widgets["game_d2k_data_dir"]
        # By its text: a text field's own clear button is a QToolButton too.
        button = next(b for b in edit.parentWidget().findChildren(QToolButton)
                      if b.text() == "…")
        with mock.patch.object(sd.QFileDialog, "getExistingDirectory",
                               return_value="/games/d2k/") as chooser:
            button.click()
        self.assertEqual(chooser.call_args.args[2], sd.browse_start(""))
        self.assertEqual(edit.text(), os.path.normpath("/games/d2k"))
        self.assertEqual(dlg.get_updated_settings()["game_d2k_data_dir"], edit.text())
        with mock.patch.object(sd.QFileDialog, "getExistingDirectory", return_value=""):
            button.click()
        self.assertEqual(edit.text(), os.path.normpath("/games/d2k"))
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            edit.setText(folder)
            with mock.patch.object(sd.QFileDialog, "getExistingDirectory",
                                   return_value="") as chooser:
                button.click()
            self.assertEqual(chooser.call_args.args[2], folder)

    def test_the_chooser_opens_at_the_nearest_existing_folder(self):
        import tempfile
        from polyhost.gui.settings_dialog import browse_start
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(browse_start(d), d)
            self.assertEqual(browse_start(os.path.join(d, "gone", "deeper")), d)
        self.assertEqual(browse_start(""), os.path.expanduser("~"))
        self.assertEqual(browse_start(os.path.join("no-such-dir-here", "deeper")), os.getcwd())


class SectionLayoutTest(unittest.TestCase):
    """Which section and group each setting is shown in."""

    def _layout(self, keys):
        from polyhost.gui.settings_dialog import layout_sections
        return layout_sections(keys)

    @staticmethod
    def _placed(layout):
        return {key: section_id for section_id, _t, groups in layout
                for _sub, keys in groups for key in keys}

    def test_every_shipped_setting_has_a_section_of_its_own(self):
        """"Other" exists so a new setting is never hidden; a shipped one
        belongs in a section that says what it is."""
        from polyhost.settings import DEFAULT_SETTINGS
        placed = self._placed(self._layout(list(DEFAULT_SETTINGS)))
        self.assertEqual(set(placed), set(DEFAULT_SETTINGS))
        self.assertEqual([k for k, s in placed.items() if s == "other"], [])

    def test_an_unknown_setting_is_shown_under_other(self):
        layout = self._layout(["ui_theme", "brand_new_setting"])
        self.assertEqual(layout[-1][0], "other")
        self.assertEqual(layout[-1][2], [(None, ["brand_new_setting"])])

    def test_developer_settings_go_to_the_developer_section(self):
        keys = ["ui_theme", "dev_mock_enabled", "developer_mode", "log_detail"]
        placed = self._placed(self._layout(keys))
        self.assertEqual((placed["dev_mock_enabled"], placed["developer_mode"],
                          placed["log_detail"]), ("developer", "general", "privacy"))

    def test_empty_sections_and_groups_are_left_out(self):
        layout = self._layout(["telemetry_enabled"])
        self.assertEqual([(s, [sub for sub, _k in g]) for s, _t, g in layout],
                         [("privacy", ["Usage report"])])

    def test_a_prefix_keeps_the_settings_order(self):
        keys = ["game_sc1_race", "game_assets_enabled", "game_cnc_data_dir"]
        games = dict((s, g) for s, _t, g in self._layout(keys))["games"]
        self.assertEqual(games, [(None, ["game_assets_enabled"]),
                                 ("Installed games", ["game_sc1_race", "game_cnc_data_dir"])])

    def test_every_section_and_subheading_is_marked_for_translation(self):
        from polyhost.gui.settings_dialog import OTHER_SECTION, SECTIONS
        strings = [OTHER_SECTION[1]] + [t for _i, t, _g in SECTIONS] + [
            sub for _i, _t, groups in SECTIONS for sub, _k in groups if sub]
        with open(os.path.join(os.path.dirname(__file__), "..", "..", "polyhost",
                               "res", "locale", "polyhost.pot"), encoding="utf-8") as f:
            pot = f.read()
        for text in strings:
            with self.subTest(text=text):
                self.assertIn(f'msgid "{text}"', pot)


class SearchMatchTest(unittest.TestCase):

    def _match(self, query, text):
        from polyhost.gui.settings_dialog import search_matches, search_words
        return search_matches(query, search_words(text))

    def test_matches_the_start_of_a_word_only(self):
        self.assertTrue(self._match("port", "Receiver port"))
        self.assertFalse(self._match("port", "USB transport reports"))

    def test_every_word_of_the_query_must_match(self):
        self.assertTrue(self._match("rec po", "Receiver port"))
        self.assertFalse(self._match("receiver token", "Receiver port"))

    def test_case_and_an_empty_query(self):
        self.assertTrue(self._match("RECEIVER", "Receiver port"))
        self.assertTrue(self._match("  ", "anything"))


@unittest.skipUnless(os.environ.get("DISPLAY")
                     or os.environ.get("QT_QPA_PLATFORM") == "offscreen",
                     "building the dialog needs a display (xvfb-run)")
class DialogBehaviourTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self, settings=None, developer_mode=False):
        from PyQt5.QtCore import QSize
        from polyhost.gui.settings_dialog import SettingsDialog
        from polyhost.settings import DEFAULT_SETTINGS
        dlg = SettingsDialog()
        self.addCleanup(dlg.deleteLater)
        dlg.setup(dict(settings if settings is not None else DEFAULT_SETTINGS),
                  developer_mode=developer_mode)
        dlg.resize(QSize(1000, 600))
        dlg.show()
        self.app.processEvents()
        return dlg

    def _wheel(self, widget):
        """One notch up: the last rows sit at the bottom of the page, where a
        notch down cannot move it."""
        from PyQt5.QtCore import QPoint, QPointF, Qt
        from PyQt5.QtGui import QWheelEvent
        from PyQt5.QtWidgets import QApplication
        pos = QPointF(widget.width() / 2, widget.height() / 2)
        event = QWheelEvent(pos, QPointF(widget.mapToGlobal(pos.toPoint())),
                            QPoint(0, 0), QPoint(0, 120), Qt.NoButton,
                            Qt.NoModifier, Qt.NoScrollPhase, False)
        QApplication.sendEvent(widget, event)
        self.app.processEvents()

    def test_the_wheel_over_an_unfocused_field_scrolls_the_page(self):
        """Scrolling past a number or a list must not change it."""
        dlg = self._dialog()
        bar = dlg.scroll.verticalScrollBar()
        for key in ("irradiance_min", "hid_reconnect_retries", "problem_scan_level"):
            with self.subTest(key=key):
                editor = dlg.edit_widgets[key]
                dlg.scroll.ensureWidgetVisible(editor)
                dlg.nav.setFocus()
                self.app.processEvents()
                before = dlg.get_updated_settings()[key]
                top = bar.value()
                self._wheel(editor)
                self.assertEqual(dlg.get_updated_settings()[key], before)
                self.assertNotEqual(bar.value(), top)

    def test_the_wheel_over_a_focused_field_changes_it(self):
        dlg = self._dialog()
        editor = dlg.edit_widgets["irradiance_min"]
        dlg.scroll.ensureWidgetVisible(editor)
        editor.setFocus()
        self.app.processEvents()
        self._wheel(editor)
        self.assertNotEqual(editor.value(), 1.8)

    def test_search_hides_what_does_not_match(self):
        dlg = self._dialog()
        before = {k for k, w in dlg.edit_widgets.items() if w.isVisibleTo(dlg)}
        dlg.search.setText("receiver port")
        shown = [k for k, w in dlg.edit_widgets.items() if w.isVisibleTo(dlg)]
        self.assertEqual(shown, ["browser_report_port"])
        visible_nav = [dlg.nav.item(i).text() for i in range(dlg.nav.count())
                       if not dlg.nav.item(i).isHidden()]
        self.assertEqual(visible_nav, ["Connections"])
        dlg.search.setText("no such setting anywhere")
        self.assertTrue(dlg._no_match.isVisibleTo(dlg))
        dlg.search.clear()
        self.assertEqual({k for k, w in dlg.edit_widgets.items() if w.isVisibleTo(dlg)},
                         before)

    def test_a_hidden_row_still_round_trips(self):
        """OK while a search hides a row must still write that row's value."""
        from polyhost.settings import DEFAULT_SETTINGS
        dlg = self._dialog(developer_mode=True)
        dlg.search.setText("receiver port")
        self.assertEqual(dlg.get_updated_settings(), dict(DEFAULT_SETTINGS))

    def test_enter_in_the_search_field_does_not_close_the_dialog(self):
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        dlg = self._dialog()
        dlg.search.setFocus()
        QTest.keyClick(dlg.search, Qt.Key_Return)
        self.assertTrue(dlg.isVisible())
        self.assertEqual(dlg.result(), 0)

    def test_choosing_a_section_scrolls_to_it(self):
        dlg = self._dialog()
        dlg.nav.setCurrentRow(dlg.nav.count() - 2)
        self.app.processEvents()
        self.assertGreater(dlg.scroll.verticalScrollBar().value(), 0)

    def test_one_section_needs_no_sidebar(self):
        """The forwarder shows a handful of General settings."""
        dlg = self._dialog({"ui_theme": "auto", "ui_language": "auto"})
        self.assertFalse(dlg.nav.parentWidget().isVisibleTo(dlg))

    @staticmethod
    def _shown(dlg):
        return {k for k, w in dlg.edit_widgets.items() if w.isVisibleTo(dlg)}

    def test_developer_settings_hidden_while_developer_mode_is_off(self):
        dlg = self._dialog()
        self.assertEqual({k for k in self._shown(dlg) if k.startswith("dev_")}, set())
        from PyQt5.QtCore import Qt
        self.assertTrue(dlg.nav.findItems("Developer", Qt.MatchExactly)[0].isHidden())

    def test_an_active_developer_setting_stays_visible_with_developer_mode_off(self):
        """It takes effect whatever developer mode says, so it must stay
        switchable: the plaintext relay listens on every interface."""
        from polyhost.settings import DEFAULT_SETTINGS
        settings = dict(DEFAULT_SETTINGS, dev_legacy_plaintext_relay=True)
        dlg = self._dialog(settings)
        self.assertEqual({k for k in self._shown(dlg) if k.startswith("dev_")},
                         {"dev_legacy_plaintext_relay"})
        developer = next(sec for sec in dlg._sections if sec.section_id == "developer")
        self.assertTrue(developer.note.isVisibleTo(dlg))
        # Turned back to its default it stays until the dialog closes, rather
        # than vanishing under the pointer.
        dlg.edit_widgets["dev_legacy_plaintext_relay"].setChecked(False)
        dlg._refilter()
        self.assertNotIn("dev_legacy_plaintext_relay", self._shown(dlg))

    def test_the_developer_switch_shows_the_section_at_once(self):
        dlg = self._dialog()
        switch = dlg.edit_widgets["developer_mode"]
        switch.setChecked(True)
        dev_keys = {k for k in dlg.edit_widgets if k.startswith("dev_")}
        self.assertTrue(dev_keys)
        self.assertLessEqual(dev_keys, self._shown(dlg))
        switch.setChecked(False)
        self.assertEqual(dev_keys & self._shown(dlg), set())

    def test_toggling_the_switch_keeps_the_scroll_position(self):
        dlg = self._dialog()
        bar = dlg.scroll.verticalScrollBar()
        bar.setValue(bar.maximum() // 2)
        top = bar.value()
        dlg.edit_widgets["developer_mode"].setChecked(True)
        self.app.processEvents()
        self.assertEqual(bar.value(), top)

    def test_a_flag_shows_the_developer_section_and_says_so(self):
        from PyQt5.QtWidgets import QLabel
        from polyhost.settings import DEFAULT_SETTINGS
        from polyhost.gui.settings_dialog import SettingsDialog
        dlg = SettingsDialog()
        self.addCleanup(dlg.deleteLater)
        dlg.setup(dict(DEFAULT_SETTINGS), developer_mode=True, flag_source="--dev")
        dlg.show()
        self.assertIn("dev_mock_enabled", self._shown(dlg))
        notes = [lbl.text() for lbl in dlg.findChildren(QLabel)
                 if lbl.objectName() == "settingsRowNote" and "--dev" in lbl.text()]
        self.assertEqual(len(notes), 2)  # developer mode and log detail

    def test_no_flag_note_without_a_flag(self):
        from PyQt5.QtWidgets import QLabel
        dlg = self._dialog(developer_mode=True)
        self.assertEqual([lbl for lbl in dlg.findChildren(QLabel)
                          if "--dev" in lbl.text()], [])

    def test_log_detail_round_trips(self):
        from polyhost.settings import DEFAULT_SETTINGS
        dlg = self._dialog(dict(DEFAULT_SETTINGS, log_detail="detailed"))
        self.assertEqual(dlg.get_updated_settings()["log_detail"], "detailed")

    def test_a_switch_mirrors_in_a_right_to_left_layout(self):
        """"On" is the end of the reading direction: right, or left in Arabic."""
        from PyQt5.QtCore import Qt
        from polyhost.gui.settings_dialog import ToggleSwitch
        images = {}
        for direction in (Qt.LeftToRight, Qt.RightToLeft):
            switch = ToggleSwitch()
            self.addCleanup(switch.deleteLater)
            switch.setLayoutDirection(direction)
            switch.setChecked(True)
            switch.resize(switch.sizeHint())
            images[direction] = switch.grab().toImage()
        def worst(a, b):
            """The largest per-channel difference. Antialiased edges round
            differently when mirrored, by 1 in a channel."""
            from PyQt5.QtGui import QColor
            return max(max(abs(p - q) for p, q in zip(QColor(a.pixel(x, y)).getRgb(),
                                                       QColor(b.pixel(x, y)).getRgb()))
                       for y in range(a.height()) for x in range(a.width()))
        ltr, rtl = images[Qt.LeftToRight], images[Qt.RightToLeft]
        self.assertLessEqual(worst(ltr.mirrored(True, False), rtl), 2)
        self.assertGreater(worst(ltr, rtl), 100)

    def test_a_divider_shows_only_between_two_visible_rows(self):
        from PyQt5.QtWidgets import QWidget
        from polyhost.gui.settings_dialog import _Group

        class Row(QWidget):
            def __init__(self, hit):
                super().__init__()
                self.available, self.hit = True, hit

            def matches(self, _query):
                return self.hit

        for hits, expected in (((True, False, True), [False, True]),
                               ((False, True, True), [False, True]),
                               ((True, True, False), [True, False]),
                               ((True, True, True), [True, True])):
            with self.subTest(hits=hits):
                group = _Group(None)
                self.addCleanup(group.deleteLater)
                for hit in hits:
                    group.add_row(Row(hit))
                group.apply_filter("q")
                self.assertEqual([d.isVisibleTo(group) for d in group._dividers], expected)

    def test_a_switch_is_still_a_checkbox(self):
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        dlg = self._dialog()
        switch = dlg.edit_widgets["telemetry_enabled"]
        dlg.scroll.ensureWidgetVisible(switch)
        self.app.processEvents()
        QTest.mouseClick(switch, Qt.LeftButton)
        self.assertFalse(dlg.get_updated_settings()["telemetry_enabled"])


if __name__ == "__main__":
    unittest.main()
