import html
import string
from collections import defaultdict

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QCursor, QGuiApplication
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QDialogButtonBox,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QSizePolicy,
    QScrollArea, QComboBox
)

from polyhost import i18n
from polyhost.i18n import _, _f, N_
from polyhost.services.game_assets import readers as game_asset_readers
from polyhost.services.os_theme import THEME_AUTO, THEME_DARK, THEME_LIGHT
from polyhost.services.problem_scan import LEVEL_ERRORS, LEVEL_ERRORS_AND_WARNINGS


def language_choices():
    """(value, label) pairs for `ui_language`.

    Every language is listed in its own name and never translated, so someone
    who picked a language they cannot read still finds theirs. "Automatic"
    names the language it resolves to, which answers "why is it German?".
    """
    from polyhost.gui.i18n_qt import os_ui_languages
    resolved = i18n.language(i18n.resolve(i18n.SETTING_AUTO, os_ui_languages()))
    auto = _f("Automatic ({language})", language=resolved.endonym)
    return [(i18n.SETTING_AUTO, auto)] + [(lang.code, lang.endonym) for lang in i18n.LANGUAGES]


# Settings whose value is one of a fixed set get a dropdown rather than the
# free-text fallback: `ui_theme` is the first one a normal user is expected to
# touch, and a typo there silently falls back to "auto" instead of doing what
# they asked. Each entry is (stored value, shown label); a callable is
# evaluated when the dialog opens.
CHOICES = {
    "ui_theme": ((THEME_AUTO, N_("Automatic")), (THEME_LIGHT, N_("Light")), (THEME_DARK, N_("Dark"))),
    "ui_language": language_choices,
    "problem_scan_level": ((LEVEL_ERRORS, N_("Errors")),
                           (LEVEL_ERRORS_AND_WARNINGS, N_("Errors and warnings"))),
}

# The shown name of each settings GROUP (the key's first word) and of each
# setting (the rest). They used to be derived from the key at render time,
# which nothing can extract for translation; the derivation survives only as
# the fallback for a key missing here, and a test keeps that list empty.
GROUP_LABELS = {
    "General": N_("General"),
    "brightness": N_("Brightness"), "browser": N_("Browser"), "daemon": N_("Daemon"),
    "delay": N_("Delay"), "dev": N_("Dev"), "developer": N_("Developer"),
    "fontpack": N_("Fontpack"), "game": N_("Game"), "generic": N_("Generic"), "hid": N_("Hid"),
    "irradiance": N_("Irradiance"), "max": N_("Max"), "problem": N_("Problem"),
    "shortcut": N_("Shortcut"), "telemetry": N_("Telemetry"), "ui": N_("Ui"),
    "unicode": N_("Unicode"), "window": N_("Window"),
}

SETTING_LABELS = {
    "unicode_send_composition_mode": N_("Send Composition Mode"),
    "brightness_set_daylight_dependent": N_("Set Daylight Dependent"),
    "brightness_allow_online_irradiance_request": N_("Allow Online Irradiance Request"),
    "brightness_allow_online_location_lookup": N_("Allow Online Location Lookup"),
    "irradiance_min": N_("Min"),
    "irradiance_max": N_("Max"),
    "irradiance_prescaler": N_("Prescaler"),
    "brightness_gamma": N_("Gamma"),
    "generic_overlays_enabled": N_("Overlays Enabled"),
    "generic_overlays_fill_gaps": N_("Overlays Add Escape Mark"),
    "generic_overlays_fill_shortcuts": N_("Overlays Add Shortcut Icons"),
    "shortcut_icons_enabled": N_("Icons Enabled"),
    "shortcut_icon_auto_fetch": N_("Icon Auto Fetch"),
    "shortcut_enable_accessibility": N_("Enable Accessibility"),
    "max_hid_message_before_delay": N_("Hid Message Before Delay"),
    "delay_time_after_max_hid_messages": N_("Time After Max Hid Messages"),
    "hid_reconnect_retries": N_("Reconnect Retries"),
    "ui_theme": N_("Theme"),
    "ui_language": N_("Language"),
    "developer_mode": N_("Mode"),
    "dev_mock_enabled": N_("Mock Enabled"),
    "dev_mock_primary": N_("Mock Primary"),
    "dev_mock_protocol": N_("Mock Protocol"),
    "dev_run_window_detection_if_not_connected_to_poly_kybd":
        N_("Run Window Detection If Not Connected To Poly Kybd"),
    "dev_win_native_set_language": N_("Win Native Set Language"),
    "dev_legacy_plaintext_relay": N_("Legacy Plaintext Relay"),
    "dev_force_hid_link": N_("Force HID Link"),
    "daemon_mode": N_("Mode"),
    "window_report_network_enabled": N_("Report Network Enabled"),
    "fontpack_auto_flash": N_("Auto Flash"),
    "fontpack_path": N_("Path"),
    "browser_url_detection": N_("Url Detection"),
    "browser_report_local_enabled": N_("Report Local Enabled"),
    "browser_report_port": N_("Report Port"),
    "browser_report_token": N_("Report Token"),
    "telemetry_enabled": N_("Enabled"),
    "telemetry_endpoint": N_("Endpoint"),
    "telemetry_install_id": N_("Install Id"),
    "problem_scan_keyboard_console": N_("Scan Keyboard Console"),
    "problem_scan_host_logs": N_("Scan Host Logs"),
    "problem_scan_level": N_("Scan Level"),
    "game_assets_enabled": N_("Art From Installed Games"),
}


# One sentence or two per setting, shown as the tooltip on its label and its
# editor. tests/gui/settings_dialog_test.py fails on a DEFAULT_SETTINGS key
# missing here, so a new setting cannot ship without one.
SETTING_DESCRIPTIONS = {
    "unicode_send_composition_mode": N_(
        "Tells the keyboard how this computer takes Unicode input (for example "
        "WinCompose), on connect and whenever it changes. Off: the keyboard keeps "
        "the mode it has stored."),
    "brightness_set_daylight_dependent": N_(
        "Sets the keycap brightness from the daylight at your location, every ten "
        "minutes."),
    "brightness_allow_online_irradiance_request": N_(
        "Asks open-meteo.com for this hour's sunlight at your location, including "
        "clouds. Off: the host computes a cloudless-sky value from the location "
        "and time."),
    "brightness_allow_online_location_lookup": N_(
        "Looks up your approximate location from your IP address (ip-api.com), "
        "once per run. Off: the brightness follows the hour of the day."),
    "irradiance_min": N_("The sunlight value that gives the dimmest brightness level."),
    "irradiance_max": N_(
        "The sunlight value that gives the brightest level. Lower it to reach full "
        "brightness on a cloudy day."),
    "irradiance_prescaler": N_("Multiplies the sunlight value before Min and Max apply."),
    "brightness_gamma": N_(
        "Shapes the daylight curve. Above 1 the middle of the day gets dimmer, "
        "below 1 brighter. The dimmest and brightest levels do not change."),
    "generic_overlays_enabled": N_(
        "Icons for apps without their own overlay: the app's mark on Escape and an "
        "icon for each of its shortcuts. Off: nothing generic is drawn for any app."),
    "generic_overlays_fill_gaps": N_(
        "An app with its own overlay also gets its mark on Escape, when the overlay "
        "leaves Escape blank."),
    "generic_overlays_fill_shortcuts": N_(
        "An app with its own overlay is also read for its shortcuts, with icons on "
        "the keys the overlay leaves blank. Reading a large app, such as a browser "
        "with a long page, can take minutes."),
    "shortcut_icons_enabled": N_(
        "Reads the focused app's shortcuts to draw an icon for each. Off: no app is "
        "read and no shortcut icons are drawn. To remove every generic icon, the "
        "Escape mark included, turn off Overlays Enabled."),
    "shortcut_icon_auto_fetch": N_(
        "Downloads icons that are missing. Off: icons already downloaded keep "
        "working, new ones are skipped."),
    "shortcut_enable_accessibility": N_(
        "Linux only. Turns on the desktop's accessibility switch so Qt and KDE apps "
        "publish their shortcuts. Off: only apps that publish them anyway (GTK) are "
        "read."),
    "max_hid_message_before_delay": N_(
        "USB transport: how many image messages are sent before a short pause, so "
        "the keyboard keeps reacting to typing. Change it only when asked to while "
        "reporting a problem."),
    "delay_time_after_max_hid_messages": N_(
        "USB transport: the length of that pause, in seconds. Change it only when "
        "asked to while reporting a problem."),
    "hid_reconnect_retries": N_(
        "How many times the host asks the keyboard for its ID before it reopens the "
        "USB connection."),
    "ui_theme": N_(
        "The look of the tray menu and dialogs. Automatic follows the desktop's "
        "light or dark setting."),
    "ui_language": N_(
        "The language of the menus and dialogs. Applies when the tray app restarts."),
    "developer_mode": N_(
        "Shows the Developer submenu in the tray menu and the developer settings in "
        "this dialog."),
    "dev_mock_enabled": N_("Adds a simulated keyboard next to the real one."),
    "dev_mock_primary": N_(
        "Uses a simulated keyboard instead of a real one, so the app runs without "
        "hardware."),
    "dev_mock_protocol": N_(
        "The protocol version the simulated keyboard reports. 0 uses the newest "
        "version this host knows."),
    "dev_run_window_detection_if_not_connected_to_poly_kybd": N_(
        "Tracks the active window even when no keyboard is connected."),
    "dev_win_native_set_language": N_(
        "Windows only, experimental. Switches the input language with Win32 calls "
        "instead of the standard method, and falls back to it on a failure."),
    "dev_force_hid_link": N_(
        "Uses the USB HID channel only, as if the keyboard had no fast link: "
        "firmware updates go over HID. For testing the HID path by hand."),
    "dev_legacy_plaintext_relay": N_(
        "Accepts window reports from old forwarders over unencrypted, "
        "unauthenticated TCP (port 50162) on every network interface. Turn it on "
        "only for an old forwarder."),
    "daemon_mode": N_(
        "Runs the keyboard connection in a background process that the tray app "
        "connects to, so the connection stays up when the tray app restarts."),
    "window_report_network_enabled": N_(
        "Accepts window reports from a forwarder on another computer. Opens a "
        "network port. Applies after a restart."),
    "fontpack_auto_flash": N_(
        "Flashes missing or outdated font-pack bundles when the keyboard connects."),
    "fontpack_path": N_(
        "A .plyf file to flash instead of the font pack that ships with the app. "
        "Empty uses the shipped pack."),
    "browser_url_detection": N_(
        "Matches overlays to the website in the focused browser tab. Off: browser "
        "overlays match on the window title only."),
    "browser_report_local_enabled": N_(
        "Runs the receiver the browser extension reports to. It listens on "
        "127.0.0.1 only."),
    "browser_report_port": N_(
        "The receiver's port. It must match the Host port in the browser extension."),
    "browser_report_token": N_(
        "A shared secret. When set, the browser extension must send the same token."),
    "telemetry_enabled": N_(
        "Sends one anonymous usage report per day: versions, operating system and a "
        "few counters. Never window titles or app names."),
    "telemetry_endpoint": N_("Where the usage report goes. Empty sends nothing."),
    "telemetry_install_id": N_(
        "The random ID of this installation, created with the first report. Delete "
        "it to count as a new installation."),
    "problem_scan_keyboard_console": N_(
        "Watches the keyboard's console for known failure messages and offers to "
        "report a problem."),
    "problem_scan_host_logs": N_("Watches this app's own log for known failure messages."),
    "problem_scan_level": N_("What counts as a problem: errors only, or errors and warnings."),
    "game_assets_enabled": N_(
        "Draws some game overlays from the game's own files when the game is "
        "installed on this computer. The images stay on this computer. Off: the "
        "shipped overlays are used."),
}

# Each game-asset reader brings its settings' labels, descriptions and choices.
for _s in game_asset_readers.all_settings():
    SETTING_LABELS[_s.key] = _s.label
    SETTING_DESCRIPTIONS[_s.key] = _s.description
    if _s.choices:
        CHOICES[_s.key] = _s.choices

# The size the dialog had before it followed the screen. It stays the minimum.
MIN_DIALOG_SIZE = QSize(640, 480)


def setting_tooltip(full_key):
    """The translated description as rich text, so Qt wraps it, or ""."""
    text = SETTING_DESCRIPTIONS.get(full_key)
    return f"<p>{html.escape(_(text))}</p>" if text else ""


def initial_dialog_size(available):
    """Half the available screen area, never below `MIN_DIALOG_SIZE`."""
    return QSize(max(MIN_DIALOG_SIZE.width(), available.width() // 2),
                 max(MIN_DIALOG_SIZE.height(), available.height() // 2))


def split_key(full_key):
    """(group, name) of a settings key, as the dialog groups it."""
    return tuple(full_key.split("_", 1)) if "_" in full_key else ("General", full_key)


def group_label(group):
    return _(GROUP_LABELS.get(group, string.capwords(group)))


def setting_label(full_key):
    derived = string.capwords(full_key, sep="_").replace("_", " ").split(" ", 1)[-1]
    return _(SETTING_LABELS.get(full_key, derived))


def _choices_for(key):
    choices = CHOICES.get(key)
    return choices() if callable(choices) else choices


def create_editor(value, key=None):
    choices = _choices_for(key)
    if choices:
        combo = QComboBox()
        for stored, label in choices:
            # A callable's labels are final; a static table's are N_-marked.
            combo.addItem(label if callable(CHOICES.get(key)) else _(label), stored)
        index = combo.findData(str(value))
        if index < 0:
            # A value outside the list (an old or hand-edited file) is kept
            # visible rather than silently replaced by the first entry on OK.
            combo.addItem(str(value), str(value))
            index = combo.count() - 1
        combo.setCurrentIndex(index)
        return combo
    if isinstance(value, bool):
        checkbox = QCheckBox()
        checkbox.setChecked(value)
        return checkbox
    elif isinstance(value, int):
        spinbox = QSpinBox()
        # ⚠️ A spin box CLAMPS the value it is given, and OK writes the clamped
        # value back. A 10_000 cap turned browser_report_port 50164 into 10000
        # on every OK, and the browser extension lost the host. Take the full
        # int range and never start the range above a stored negative value.
        spinbox.setRange(-2_147_483_648 if value < 0 else 0, 2_147_483_647)
        spinbox.setValue(value)
        return spinbox
    elif isinstance(value, float):
        doublebox = QDoubleSpinBox()
        doublebox.setDecimals(3)
        # No clamp, as above, and room to move past a stored value in either
        # direction rather than pinning it to an end of the range.
        doublebox.setRange(min(-1e9, value * 10) if value < 0 else 0.0,
                           max(1_000.0, abs(value) * 10))
        # Default step is 1.0, which silently clamps fine-grained float settings
        # (e.g. the 0.75 brightness prescaler) to 0.0 on a single scroll/click —
        # use a small step so these stay editable to their real precision.
        doublebox.setSingleStep(0.05)
        doublebox.setValue(value)
        return doublebox
    else:  # string fallback
        line_edit = QLineEdit()
        line_edit.setText(str(value))
        return line_edit


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("PolyKybd Settings"))
        self.edit_widgets = {}
        self._all_settings = {}

    def sizeHint(self):
        return MIN_DIALOG_SIZE

    def _fit_to_screen(self):
        """Open at half the screen the cursor is on, with the old size as minimum."""
        self.setMinimumSize(MIN_DIALOG_SIZE)
        screen = (QGuiApplication.screenAt(QCursor.pos())
                  or QGuiApplication.primaryScreen())
        if screen is not None:
            self.resize(initial_dialog_size(screen.availableGeometry().size()))

    def setup(self, settings_dict, developer_mode=False):
        self._all_settings = dict(settings_dict)
        # No setWindowIcon here: the dialog inherits QApplication's, which
        # IconStateManager already sets to the right mark for whichever app
        # opened it (the P for the tray app, the F for the forwarder). Pinning
        # pcolor.png put the tray app's mark on the forwarder's Settings window.

        # Outer layout
        main_layout = QVBoxLayout(self)

        title_label = QLabel(_("Some settings might need a restart to take effect."))
        title_label.setAlignment(Qt.AlignCenter)
        # Wraps rather than clips: the German sentence is wider than 640 px.
        title_label.setWordWrap(True)
        main_layout.addWidget(title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_contents = QWidget()
        scroll_layout = QVBoxLayout(scroll_contents)

        grouped_settings = defaultdict(dict)
        for full_key, value in settings_dict.items():
            if full_key.startswith("dev_") and not developer_mode:
                continue
            group, _name = split_key(full_key)
            grouped_settings[group][full_key] = value

        # For each group, create a QGroupBox with a form layout
        for group_name, group_items in grouped_settings.items():
            group_box = QGroupBox(group_label(group_name))
            group_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            group_layout = QFormLayout()
            group_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            group_box.setLayout(group_layout)

            for full_key, value in group_items.items():
                label = QLabel(setting_label(full_key))
                label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                widget = create_editor(value, full_key)
                tooltip = setting_tooltip(full_key)
                if tooltip:
                    label.setToolTip(tooltip)
                    widget.setToolTip(tooltip)

                field_container = QWidget()
                field_layout = QHBoxLayout()
                field_layout.setContentsMargins(0, 0, 0, 0)
                field_layout.setAlignment(Qt.AlignRight)  # Right-align the widget inside the field cell
                field_layout.addWidget(widget)
                field_container.setLayout(field_layout)

                group_layout.addRow(label, field_container)
                self.edit_widgets[full_key] = widget

            # form_wrapper_layout.addWidget(group_box)
            scroll_layout.addWidget(group_box)

        scroll_layout.addStretch()  # force groups to fill width
        scroll.setWidget(scroll_contents)
        main_layout.addWidget(scroll)

        # No device actions here: this dialog edits settings. The glyph-script
        # reset button was removed (2026-10-16) because the tray's Keycap Script
        # menu has "Standard" as its first entry; the Eden replay lives in
        # `polyctl replay-anim`.

        # Add buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons, alignment=Qt.AlignCenter)
        self._fit_to_screen()

    def get_updated_settings(self):
        updated = dict(self._all_settings)
        for key, widget in self.edit_widgets.items():
            if isinstance(widget, QCheckBox):
                updated[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                updated[key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                updated[key] = widget.value()
            elif isinstance(widget, QComboBox):
                updated[key] = widget.currentData()
            elif isinstance(widget, QLineEdit):
                updated[key] = widget.text()
        return updated
