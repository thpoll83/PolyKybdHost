import html
import os
import re
import string

from PyQt5.QtCore import QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPalette, QPen
from PyQt5.QtWidgets import (
    QAbstractScrollArea, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QScrollArea, QSpinBox,
    QToolButton, QVBoxLayout, QWidget,
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


def emoji_dict_choices():
    """The shipped emoji search dictionaries, as (id, "native — English")."""
    from polyhost.services import emojidict
    manifest = emojidict.load_manifest()
    return [(e["id"], emojidict.label(e)) for e in (manifest or {}).get("dictionaries", [])]


# Settings whose value is one of a fixed set get a dropdown rather than the
# free-text fallback: `ui_theme` is the first one a normal user is expected to
# touch, and a typo there silently falls back to "auto" instead of doing what
# they asked. Each entry is (stored value, shown label); a callable is
# evaluated when the dialog opens.
CHOICES = {
    "ui_theme": ((THEME_AUTO, N_("Automatic")), (THEME_LIGHT, N_("Light")), (THEME_DARK, N_("Dark"))),
    "ui_language": language_choices,
    "emoji_search_dict": emoji_dict_choices,
    "problem_scan_level": ((LEVEL_ERRORS, N_("Errors")),
                           (LEVEL_ERRORS_AND_WARNINGS, N_("Errors and warnings"))),
}

# The dialog's sections, in sidebar order. Each is (id, title, groups), and each
# group is (subheading or None, keys). A key that ends in "*" takes every
# setting with that prefix, in the order the settings dict lists them. A setting
# no section names is shown under "Other", so a new setting is never hidden;
# tests/gui/settings_dialog_test.py keeps "Other" empty for the shipped ones.
SECTIONS = (
    ("general", N_("General"), (
        (None, ("ui_theme", "ui_language", "daemon_mode", "developer_mode")),
    )),
    ("icons", N_("Keycap icons"), (
        (None, ("generic_overlays_enabled", "shortcut_icons_enabled",
                "shortcut_icon_auto_fetch", "browser_url_detection")),
        (N_("Apps with their own overlay"), ("generic_overlays_fill_gaps",
                                             "generic_overlays_fill_shortcuts")),
        (N_("Linux"), ("shortcut_enable_accessibility",)),
    )),
    ("games", N_("Games"), (
        (None, ("game_assets_enabled",)),
        (N_("Installed games"), ("game_*",)),
    )),
    ("brightness", N_("Brightness"), (
        (None, ("brightness_set_daylight_dependent",
                "brightness_allow_online_location_lookup",
                "brightness_allow_online_irradiance_request")),
        (N_("Daylight curve"), ("irradiance_min", "irradiance_max",
                                "irradiance_prescaler", "brightness_gamma")),
    )),
    ("keyboard", N_("Keyboard data"), (
        (None, ("unicode_send_composition_mode",)),
        (N_("Font packs"), ("fontpack_auto_flash", "fontpack_path")),
        (N_("Emoji search"), ("emoji_search_dict", "emoji_search_dict_file")),
    )),
    ("connections", N_("Connections"), (
        (N_("Browser extension"), ("browser_report_local_enabled",
                                   "browser_report_port", "browser_report_token")),
        (N_("Forwarders"), ("window_report_network_enabled",)),
        (N_("USB transport"), ("hid_reconnect_retries", "max_hid_message_before_delay",
                               "delay_time_after_max_hid_messages")),
    )),
    ("privacy", N_("Privacy and diagnostics"), (
        (N_("Usage report"), ("telemetry_*",)),
        (N_("Problem detection"), ("problem_scan_*",)),
    )),
    ("developer", N_("Developer"), (
        (None, ("dev_*",)),
    )),
)
OTHER_SECTION = ("other", N_("Other"))

SETTING_LABELS = {
    "unicode_send_composition_mode": N_("Send Unicode input mode"),
    "brightness_set_daylight_dependent": N_("Follow daylight"),
    "brightness_allow_online_irradiance_request": N_("Online sunlight data"),
    "brightness_allow_online_location_lookup": N_("Online location lookup"),
    "irradiance_min": N_("Sunlight at dimmest"),
    "irradiance_max": N_("Sunlight at brightest"),
    "irradiance_prescaler": N_("Sunlight scale"),
    "brightness_gamma": N_("Curve gamma"),
    "generic_overlays_enabled": N_("Generic icons"),
    "generic_overlays_fill_gaps": N_("Add the Escape mark"),
    "generic_overlays_fill_shortcuts": N_("Add shortcut icons"),
    "shortcut_icons_enabled": N_("Shortcut icons"),
    "shortcut_icon_auto_fetch": N_("Download missing icons"),
    "shortcut_enable_accessibility": N_("Turn on accessibility"),
    "max_hid_message_before_delay": N_("Messages before a pause"),
    "delay_time_after_max_hid_messages": N_("Pause length (s)"),
    "hid_reconnect_retries": N_("ID requests before reconnect"),
    "ui_theme": N_("Theme"),
    "ui_language": N_("Language"),
    "developer_mode": N_("Developer mode"),
    "dev_mock_enabled": N_("Mock Enabled"),
    "dev_mock_primary": N_("Mock Primary"),
    "dev_mock_protocol": N_("Mock Protocol"),
    "dev_run_window_detection_if_not_connected_to_poly_kybd":
        N_("Run Window Detection If Not Connected To Poly Kybd"),
    "dev_win_native_set_language": N_("Win Native Set Language"),
    "dev_legacy_plaintext_relay": N_("Legacy Plaintext Relay"),
    "dev_force_hid_link": N_("Force HID Link"),
    "daemon_mode": N_("Background service"),
    "window_report_network_enabled": N_("Accept forwarders"),
    "fontpack_auto_flash": N_("Update on connect"),
    "emoji_search_dict": N_("Search language"),
    "emoji_search_dict_file": N_("Own dictionary file"),
    "fontpack_path": N_("Font pack file"),
    "browser_url_detection": N_("Match websites"),
    "browser_report_local_enabled": N_("Receive browser reports"),
    "browser_report_port": N_("Receiver port"),
    "browser_report_token": N_("Receiver token"),
    "telemetry_enabled": N_("Send usage report"),
    "telemetry_endpoint": N_("Report address"),
    "telemetry_install_id": N_("Installation ID"),
    "problem_scan_keyboard_console": N_("Watch the keyboard console"),
    "problem_scan_host_logs": N_("Watch this app's log"),
    "problem_scan_level": N_("What counts as a problem"),
    "game_assets_enabled": N_("Art from installed games"),
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
    "irradiance_prescaler": N_("Multiplies the sunlight value before the dimmest and brightest values apply."),
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
        "Escape mark included, turn off Generic icons."),
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
    "emoji_search_dict": N_(
        "The language the keyboard's emoji layer searches in. The keyboard gets "
        "the dictionary right away when you change this, and when it connects if "
        "Update on connect is on. Own dictionary file, when set, is used instead."),
    "emoji_search_dict_file": N_(
        "A dictionary you built yourself (.plyd), used instead of Search language. "
        "Empty: the shipped dictionary is used. Choose it in the tray to flash it "
        "right away."),
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

# Settings that hold a folder: each game-asset reader's folder to read from. Their
# rows get a "…" button that opens a folder chooser.
FOLDER_KEYS = frozenset(r.folder for r in game_asset_readers.READERS.values() if r.folder)

# The size the dialog had before it followed the screen. It stays the minimum.
MIN_DIALOG_SIZE = QSize(640, 480)
# The settings column stops growing here, so a label and its control stay close
# together on a wide window.
CONTENT_MAX_WIDTH = 760
SIDEBAR_WIDTH = 210


def setting_tooltip(full_key):
    """The translated description as rich text, so Qt wraps it, or ""."""
    text = SETTING_DESCRIPTIONS.get(full_key)
    return f"<p>{html.escape(_(text))}</p>" if text else ""


def setting_description(full_key):
    """The translated description as plain text, or ""."""
    text = SETTING_DESCRIPTIONS.get(full_key)
    return _(text) if text else ""


def initial_dialog_size(available):
    """Half the available screen area, never below `MIN_DIALOG_SIZE`."""
    return QSize(max(MIN_DIALOG_SIZE.width(), available.width() // 2),
                 max(MIN_DIALOG_SIZE.height(), available.height() // 2))


def setting_label(full_key):
    derived = string.capwords(full_key, sep="_").replace("_", " ")
    return _(SETTING_LABELS.get(full_key, derived))


_WORD = re.compile(r"\w+", re.UNICODE)


def search_words(text):
    """The casefolded words of `text`, for :func:`search_matches`."""
    return _WORD.findall(text.casefold())


def search_matches(query, words):
    """Every word of `query` starts some word in `words`. An empty query matches.

    Word starts, not substrings: "port" finds "Receiver port" but not
    "reports" or "transport"."""
    return all(any(w.startswith(q) for w in words) for q in search_words(query))


def _matches(pattern, key):
    return key.startswith(pattern[:-1]) if pattern.endswith("*") else key == pattern


def layout_sections(keys, developer_mode=False):
    """Place `keys` into the dialog's sections.

    Returns ``[(section_id, title, [(subheading, [key, ...]), ...]), ...]`` in
    sidebar order, with empty groups and sections left out. The ``dev_`` keys
    appear only in developer mode. Keys no section names go to "Other", last.
    """
    keys = [k for k in keys if developer_mode or not k.startswith("dev_")]
    placed = set()
    out = []
    for section_id, title, groups in SECTIONS:
        built = []
        for subheading, patterns in groups:
            members = []
            for pattern in patterns:
                for key in keys:
                    if key not in placed and _matches(pattern, key):
                        members.append(key)
                        placed.add(key)
            if members:
                built.append((subheading, members))
        if built:
            out.append((section_id, title, built))
    rest = [k for k in keys if k not in placed]
    if rest:
        out.append((OTHER_SECTION[0], OTHER_SECTION[1], [(None, rest)]))
    return out


def _choices_for(key):
    choices = CHOICES.get(key)
    return choices() if callable(choices) else choices


# ⚠️ A spin box or a combo box under the pointer takes the wheel even without
# focus, so scrolling the page changed whatever value passed under the pointer.
# These take the wheel only once clicked or tabbed into. Otherwise the event goes
# to the enclosing scroll area. It is forwarded, not ignored: Qt 5 passes an
# ignored wheel event to the parent only when it came from the mouse, so an
# ignored one would scroll nothing in every other case.
class _WheelOnFocus:
    def _init_wheel(self):
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
            return
        area = self.parentWidget()
        while area is not None and not isinstance(area, QAbstractScrollArea):
            area = area.parentWidget()
        if area is not None:
            QApplication.sendEvent(area.verticalScrollBar(), event)
        event.accept()


class SettingSpinBox(_WheelOnFocus, QSpinBox):
    def __init__(self, *args):
        super().__init__(*args)
        self._init_wheel()


class SettingDoubleSpinBox(_WheelOnFocus, QDoubleSpinBox):
    def __init__(self, *args):
        super().__init__(*args)
        self._init_wheel()


class SettingComboBox(_WheelOnFocus, QComboBox):
    def __init__(self, *args):
        super().__init__(*args)
        self._init_wheel()


class ToggleSwitch(QCheckBox):
    """An on/off switch. A QCheckBox underneath, so keyboard, accessibility and
    `isChecked()` behave as before; only the drawing differs."""

    TRACK = QSize(38, 22)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self):
        return self.TRACK + QSize(4, 4)

    def minimumSizeHint(self):
        return self.sizeHint()

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        track = QRectF(2, (self.height() - self.TRACK.height()) / 2,
                       self.TRACK.width(), self.TRACK.height())
        radius = track.height() / 2
        if not self.isEnabled():
            fill = pal.color(QPalette.Disabled, QPalette.Mid)
        elif self.isChecked():
            fill = pal.color(QPalette.Highlight)
        else:
            fill = pal.color(QPalette.Mid)
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(track, radius, radius)
        knob_d = track.height() - 6
        x = track.right() - 3 - knob_d if self.isChecked() else track.left() + 3
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(x, track.top() + 3, knob_d, knob_d))
        if self.hasFocus():
            ring = QPen(pal.color(QPalette.Highlight))
            ring.setWidthF(1.5)
            painter.setPen(ring)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(track.adjusted(-1.5, -1.5, 1.5, 1.5),
                                    radius + 1.5, radius + 1.5)


def create_editor(value, key=None):
    choices = _choices_for(key)
    if choices:
        combo = SettingComboBox()
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
        # Sized to its entries, but capped: the emoji dictionary list has
        # long "native — English" names that squeezed the description.
        combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        combo.setMinimumWidth(160)
        combo.setMaximumWidth(260)
        return combo
    if isinstance(value, bool):
        switch = ToggleSwitch()
        switch.setChecked(value)
        return switch
    elif isinstance(value, int):
        spinbox = SettingSpinBox()
        # ⚠️ A spin box CLAMPS the value it is given, and OK writes the clamped
        # value back. A 10_000 cap turned browser_report_port 50164 into 10000
        # on every OK, and the browser extension lost the host. Take the full
        # int range and never start the range above a stored negative value.
        spinbox.setRange(-2_147_483_648 if value < 0 else 0, 2_147_483_647)
        spinbox.setValue(value)
        spinbox.setFixedWidth(120)
        return spinbox
    elif isinstance(value, float):
        doublebox = SettingDoubleSpinBox()
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
        doublebox.setFixedWidth(120)
        return doublebox
    else:  # string fallback
        line_edit = QLineEdit()
        line_edit.setText(str(value))
        line_edit.setClearButtonEnabled(True)
        return line_edit


def browse_start(text):
    """The folder a chooser opens at: the folder in `text` when it exists,
    else its nearest existing parent, else the home folder."""
    # A relative value is read from the working folder, so start the walk there.
    path = os.path.abspath(os.path.expanduser(text.strip())) if text.strip() else ""
    while path and not os.path.isdir(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return path if path and os.path.isdir(path) else os.path.expanduser("~")


# The look of the cards. Every colour is a palette role, so the light and the
# dark theme (gui/theme.py) both apply without a second stylesheet.
_STYLE = """
QFrame#settingsCard {
    background: palette(base);
    border: 1px solid palette(mid);
    border-radius: 8px;
}
QFrame#settingsDivider { background: palette(midlight); border: none; }
QLabel#settingsSectionTitle { font-size: 15pt; font-weight: 600; }
QLabel#settingsSubheading { font-weight: 600; color: palette(text); }
QListWidget#settingsNav {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget#settingsNav::item {
    padding: 7px 10px;
    border-radius: 6px;
    margin: 1px 0px;
}
QListWidget#settingsNav::item:selected {
    background: palette(highlight);
    color: palette(highlighted-text);
}
"""


class _SearchField(QLineEdit):
    """The search field. Enter does nothing, rather than pressing OK."""

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            event.accept()
            return
        super().keyPressEvent(event)


class _SettingRow(QWidget):
    """One setting: its label, the description below it, and its control.

    A short control (switch, number, list) sits on the right of the text. A
    text field takes the full row width below the text, because a path or a
    URL squeezed beside a description is unreadable.
    """

    def __init__(self, full_key, editor, extra=None, parent=None):
        super().__init__(parent)
        self.full_key = full_key
        title = setting_label(full_key)
        description = setting_description(full_key)
        self.search_words = search_words(f"{title} {description} {full_key}")

        title_lbl = QLabel(title)
        title_lbl.setWordWrap(True)
        title_lbl.setToolTip(setting_tooltip(full_key))
        title_lbl.setBuddy(editor)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.addWidget(title_lbl)
        if description:
            desc_lbl = QLabel(description)
            desc_lbl.setWordWrap(True)
            desc_lbl.setObjectName("settingsDescription")
            font = desc_lbl.font()
            font.setPointSizeF(max(font.pointSizeF() * 0.88, 7.0))
            desc_lbl.setFont(font)
            muted = desc_lbl.palette()
            muted.setColor(QPalette.WindowText,
                           muted.color(QPalette.Disabled, QPalette.WindowText))
            desc_lbl.setPalette(muted)
            text_col.addWidget(desc_lbl)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(6)
        if isinstance(editor, QLineEdit):
            outer.addLayout(text_col)
            field = QWidget()
            field_row = QHBoxLayout(field)
            field_row.setContentsMargins(0, 0, 0, 0)
            field_row.setSpacing(6)
            field_row.addWidget(editor, 1)
            if extra is not None:
                field_row.addWidget(extra)
            outer.addWidget(field)
        else:
            row = QHBoxLayout()
            row.setSpacing(16)
            row.addLayout(text_col, 1)
            field = QWidget()
            field_row = QHBoxLayout(field)
            field_row.setContentsMargins(0, 0, 0, 0)
            field_row.addWidget(editor)
            row.addWidget(field, 0, Qt.AlignVCenter)
            outer.addLayout(row)

    def matches(self, query):
        return search_matches(query, self.search_words)


class _Group(QWidget):
    """An optional subheading over a card of rows."""

    def __init__(self, subheading, parent=None):
        super().__init__(parent)
        self.subheading = _(subheading) if subheading else ""
        self.rows = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        if self.subheading:
            head = QLabel(self.subheading)
            head.setObjectName("settingsSubheading")
            lay.addWidget(head)
        self.card = QFrame()
        self.card.setObjectName("settingsCard")
        self._card_lay = QVBoxLayout(self.card)
        self._card_lay.setContentsMargins(0, 2, 0, 2)
        self._card_lay.setSpacing(0)
        lay.addWidget(self.card)
        self._dividers = []

    def add_row(self, row):
        if self.rows:
            line = QFrame()
            line.setObjectName("settingsDivider")
            line.setFixedHeight(1)
            self._card_lay.addWidget(line)
            self._dividers.append(line)
        self.rows.append(row)
        self._card_lay.addWidget(row)

    def apply_filter(self, query):
        """Show the matching rows; a subheading match shows the whole group."""
        whole = bool(query) and search_matches(query, search_words(self.subheading))
        shown = [r for r in self.rows if whole or r.matches(query)]
        for r in self.rows:
            r.setVisible(r in shown)
        # A divider sits above every row but the first; show one only between
        # two visible rows.
        seen = False
        for line, r in zip(self._dividers, self.rows[1:]):
            idx = self.rows.index(r)
            seen = any(x in shown for x in self.rows[:idx])
            line.setVisible(seen and r in shown)
        self.setVisible(bool(shown))
        return bool(shown)


class _Section(QWidget):
    def __init__(self, section_id, title, parent=None):
        super().__init__(parent)
        self.section_id = section_id
        self.title = _(title)
        self.groups = []
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(14)
        head = QLabel(self.title)
        head.setObjectName("settingsSectionTitle")
        self._lay.addWidget(head)

    def add_group(self, group):
        self.groups.append(group)
        self._lay.addWidget(group)

    def apply_filter(self, query):
        visible = [g.apply_filter(query) for g in self.groups]
        self.setVisible(any(visible))
        return any(visible)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("PolyKybd Settings"))
        self.edit_widgets = {}
        self._all_settings = {}
        self._sections = []
        self._syncing_nav = False

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
        self.setStyleSheet(_STYLE)
        layout = layout_sections(settings_dict, developer_mode)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        main.addLayout(body, 1)

        # Sidebar: the search field and the section list.
        side = QWidget()
        side.setFixedWidth(SIDEBAR_WIDTH)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(12, 14, 8, 12)
        side_lay.setSpacing(10)
        self.search = _SearchField()
        self.search.setPlaceholderText(_("Search settings"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        side_lay.addWidget(self.search)
        self.nav = QListWidget()
        self.nav.setObjectName("settingsNav")
        self.nav.setFrameShape(QFrame.NoFrame)
        self.nav.setWordWrap(True)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav.currentRowChanged.connect(self._nav_selected)
        side_lay.addWidget(self.nav, 1)
        body.addWidget(side)
        # One section needs no list (the forwarder shows a handful of keys).
        side.setVisible(len(layout) > 1)

        # The settings column, scrolled.
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        holder_lay = QHBoxLayout(holder)
        holder_lay.setContentsMargins(16, 14, 16, 24)
        column = QWidget()
        column.setMaximumWidth(CONTENT_MAX_WIDTH)
        col_lay = QVBoxLayout(column)
        col_lay.setContentsMargins(0, 0, 0, 0)
        col_lay.setSpacing(28)
        holder_lay.addWidget(column, 1)
        holder_lay.addStretch(0)

        for section_id, title, groups in layout:
            section = _Section(section_id, title)
            for subheading, keys in groups:
                group = _Group(subheading)
                for full_key in keys:
                    group.add_row(self._make_row(full_key, settings_dict[full_key]))
                section.add_group(group)
            col_lay.addWidget(section)
            self._sections.append(section)
            self.nav.addItem(QListWidgetItem(section.title))
        self._no_match = QLabel(_("No setting matches the search."))
        self._no_match.setAlignment(Qt.AlignCenter)
        self._no_match.hide()
        col_lay.addWidget(self._no_match)
        col_lay.addStretch(1)
        self.scroll.setWidget(holder)
        self.scroll.verticalScrollBar().valueChanged.connect(self._sync_nav)
        body.addWidget(self.scroll, 1)

        # No device actions here: this dialog edits settings. The glyph-script
        # reset button was removed (2026-10-16) because the tray's Keycap Script
        # menu has "Standard" as its first entry; the Eden replay lives in
        # `polyctl replay-anim`.
        footer = QHBoxLayout()
        footer.setContentsMargins(16, 8, 16, 12)
        note = QLabel(_("Some settings might need a restart to take effect."))
        note.setWordWrap(True)
        muted = note.palette()
        muted.setColor(QPalette.WindowText, muted.color(QPalette.Disabled, QPalette.WindowText))
        note.setPalette(muted)
        footer.addWidget(note, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        main.addLayout(footer)

        if self.nav.count():
            self.nav.setCurrentRow(0)
        self._fit_to_screen()

    def _make_row(self, full_key, value):
        editor = create_editor(value, full_key)
        tooltip = setting_tooltip(full_key)
        if tooltip:
            editor.setToolTip(tooltip)
        editor.setAccessibleName(setting_label(full_key))
        extra = None
        if full_key in FOLDER_KEYS and isinstance(editor, QLineEdit):
            extra = self._browse_button(full_key, editor)
        self.edit_widgets[full_key] = editor
        return _SettingRow(full_key, editor, extra)

    def _nav_selected(self, row):
        if self._syncing_nav or not 0 <= row < len(self._sections):
            return
        section = self._sections[row]
        if section.isVisible():
            self.scroll.verticalScrollBar().setValue(section.parentWidget().mapTo(
                self.scroll.widget(), section.pos()).y())

    def _sync_nav(self, value):
        """Select the section at the top of the view as the page scrolls."""
        current = 0
        holder = self.scroll.widget()
        for i, section in enumerate(self._sections):
            if not section.isVisible():
                continue
            top = section.parentWidget().mapTo(holder, section.pos()).y()
            if top <= value + 40:
                current = i
        bar = self.scroll.verticalScrollBar()
        if value >= bar.maximum() and bar.maximum() > 0:
            visible = [i for i, s in enumerate(self._sections) if s.isVisible()]
            current = visible[-1] if visible else current
        self._syncing_nav = True
        self.nav.setCurrentRow(current)
        self._syncing_nav = False

    def _apply_filter(self, text):
        query = text.strip().casefold()
        any_shown = False
        for i, section in enumerate(self._sections):
            shown = section.apply_filter(query)
            any_shown = any_shown or shown
            self.nav.item(i).setHidden(not shown)
        self._no_match.setVisible(not any_shown)
        self.scroll.verticalScrollBar().setValue(0)

    def _browse_button(self, full_key, line_edit):
        button = QToolButton()
        button.setText("…")
        button.setToolTip(_("Browse…"))
        button.setAccessibleName(_("Browse…"))
        button.clicked.connect(lambda: self._browse_folder(full_key, line_edit))
        return button

    def _browse_folder(self, full_key, line_edit):
        """Put the folder the user picks into `line_edit`; Cancel keeps it."""
        folder = QFileDialog.getExistingDirectory(
            self, setting_label(full_key), browse_start(line_edit.text()))
        if folder:
            line_edit.setText(os.path.normpath(folder))

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
