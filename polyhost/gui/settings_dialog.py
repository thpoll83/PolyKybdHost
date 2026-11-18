import html
import os
import re
import string

from PyQt5.QtCore import QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPalette, QPen
from PyQt5.QtWidgets import (
    QAbstractScrollArea, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QScrollArea, QSpinBox,
    QToolButton, QVBoxLayout, QWidget,
)

from polyhost import i18n
from polyhost.gui import keyboard_settings as kbd
from polyhost.gui import section_colors, section_style
from polyhost.gui.section_style import ColorSection
from polyhost.gui.theme import is_dark
from polyhost.gui.ui_kit import set_button_icon, style_button_box, px
from polyhost.i18n import _, _f, N_
from polyhost.services.game_assets import readers as game_asset_readers
from polyhost.services.os_theme import THEME_AUTO, THEME_DARK, THEME_LIGHT
from polyhost.services.problem_scan import LEVEL_ERRORS, LEVEL_ERRORS_AND_WARNINGS
from polyhost.settings import DEFAULT_SETTINGS
from polyhost.device.command_ids import TapTerms


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
    "log_detail": (("normal", N_("Normal")), ("debug", N_("Debug")),
                   ("detailed", N_("Detailed"))),
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
    ("brightness", N_("Brightness"), (
        (None, (kbd.BRIGHTNESS, "brightness_set_daylight_dependent",
                "brightness_allow_online_location_lookup",
                "brightness_allow_online_irradiance_request")),
        (N_("Daylight curve"), ("irradiance_min", "irradiance_max",
                                "irradiance_prescaler", "brightness_gamma")),
    )),
    # The kbd_ rows are stored on the keyboard (gui/keyboard_settings.py); the
    # dialog reads them when it opens and sends a change on OK.
    ("keyboard", N_("Keyboard"), (
        (N_("Idle display"), (kbd.IDLE_STYLE, kbd.IDLE_TIMEOUT)),
        (N_("Keycaps"), (kbd.GLYPH_SCRIPT, kbd.GLYPH_PLACEMENT, kbd.GLYPH_SIZE)),
        (N_("Tap-Hold Timing"), kbd.TAP_KEYS),
        (N_("Unicode input"), ("unicode_send_composition_mode",)),
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
    ("icons", N_("Keycap icons"), (
        (None, ("generic_overlays_enabled", "shortcut_icons_enabled",
                "shortcut_icon_auto_fetch", "browser_url_detection")),
        (N_("Apps with their own overlay"), ("generic_overlays_fill_gaps",
                                             "generic_overlays_fill_shortcuts")),
        (N_("Linux"), ("shortcut_enable_accessibility",)),
    )),
    ("agents", N_("AI agents"), (
        (None, ("agents_enabled", "agents_title_scan", "agents_download_fonts",
                "agents_dictation_shortcut",
                "agents_remote_enabled", "agents_raise_here", "agents_stale_minutes",
                "agents_forget_minutes")),
    )),
    ("games", N_("Games"), (
        (None, ("game_assets_enabled",)),
        (N_("Installed games"), ("game_*",)),
    )),
    ("privacy", N_("Privacy and diagnostics"), (
        (N_("Usage report"), ("telemetry_*",)),
        (N_("Problem detection"), ("problem_scan_*",)),
        (N_("Logs"), ("log_detail",)),
    )),
    ("developer", N_("Developer"), (
        (None, ("dev_*",)),
    )),
)
OTHER_SECTION = ("other", N_("Other"))

# Rows most users never change. A section that has any gets an Advanced switch
# in its title band; with the switch off these rows are hidden. A search shows
# them whatever the switch says, so a search never hides a setting.
ADVANCED_SETTINGS = frozenset((
    "irradiance_min", "irradiance_max", "irradiance_prescaler", "brightness_gamma",
    kbd.GLYPH_PLACEMENT, kbd.FLOW_TAP_TERM, kbd.AUTO_SHIFT_MS,
    "fontpack_path", "emoji_search_dict_file",
    "browser_report_port", "browser_report_token", "hid_reconnect_retries",
    "max_hid_message_before_delay", "delay_time_after_max_hid_messages",
    "shortcut_enable_accessibility",
    "agents_download_fonts", "agents_stale_minutes", "agents_forget_minutes",
    "telemetry_endpoint", "telemetry_install_id",
))

SETTING_LABELS = {
    "unicode_send_composition_mode": N_("Send Unicode input mode"),
    kbd.BRIGHTNESS: N_("Keycap brightness"),
    kbd.IDLE_STYLE: N_("Idle animation"),
    kbd.IDLE_TIMEOUT: N_("Idle After"),
    kbd.GLYPH_SCRIPT: N_("Keycap Script"),
    kbd.GLYPH_PLACEMENT: N_("Script placement"),
    kbd.GLYPH_SIZE: N_("Keycap Size"),
    kbd.TAPPING_TERM: N_("Tapping term"),
    kbd.FLOW_TAP_TERM: N_("Flow Tap term"),
    kbd.AUTO_SHIFT: N_("Auto Shift"),
    kbd.AUTO_SHIFT_MS: N_("Auto Shift timeout"),
    "brightness_set_daylight_dependent": N_("Follow daylight"),
    "brightness_allow_online_irradiance_request": N_("Online sunlight data"),
    "brightness_allow_online_location_lookup": N_("Online location lookup"),
    "irradiance_min": N_("Sunlight at dimmest"),
    "irradiance_max": N_("Sunlight at brightest"),
    "irradiance_prescaler": N_("Sunlight scale"),
    "brightness_gamma": N_("Curve gamma"),
    "generic_overlays_enabled": N_("Icons for apps without an overlay"),
    "generic_overlays_fill_gaps": N_("Add the Escape mark"),
    "generic_overlays_fill_shortcuts": N_("Add icons from the app's menus"),
    "shortcut_icons_enabled": N_("Read shortcuts from app menus"),
    "shortcut_icon_auto_fetch": N_("Download icons from the internet"),
    "shortcut_enable_accessibility": N_("Turn on accessibility"),
    "max_hid_message_before_delay": N_("Messages before a pause"),
    "delay_time_after_max_hid_messages": N_("Pause length (s)"),
    "hid_reconnect_retries": N_("ID requests before reconnect"),
    "ui_theme": N_("Theme"),
    "ui_language": N_("Language"),
    "developer_mode": N_("Developer mode"),
    "log_detail": N_("Log detail"),
    "dev_mock_enabled": N_("Add a simulated keyboard"),
    "dev_mock_primary": N_("Simulated keyboard only"),
    "dev_mock_protocol": N_("Simulated protocol version"),
    "dev_run_window_detection_if_not_connected_to_poly_kybd": N_("Track windows without a keyboard"),
    "dev_win_native_set_language": N_("Native Windows language switch"),
    "dev_legacy_plaintext_relay": N_("Legacy plaintext relay"),
    "dev_force_hid_link": N_("Force the HID link"),
    "daemon_mode": N_("Background service"),
    "window_report_network_enabled": N_("Accept forwarders"),
    "fontpack_auto_flash": N_("Send font packs on connect"),
    "emoji_search_dict": N_("Search language"),
    "emoji_search_dict_file": N_("Own dictionary file"),
    "fontpack_path": N_("Font pack file"),
    "browser_url_detection": N_("Match the website in the browser"),
    "browser_report_local_enabled": N_("Receive browser reports"),
    "browser_report_port": N_("Receiver port"),
    "browser_report_token": N_("Receiver token"),
    "telemetry_enabled": N_("Send usage report"),
    "telemetry_endpoint": N_("Report address"),
    "telemetry_install_id": N_("Installation ID"),
    "problem_scan_keyboard_console": N_("Watch the keyboard's messages"),
    "problem_scan_host_logs": N_("Watch this app's log"),
    "problem_scan_level": N_("What counts as a problem"),
    "game_assets_enabled": N_("Art from installed games"),
    "agents_enabled": N_("Show on the number row"),
    "agents_title_scan": N_("Find by window title"),
    "agents_download_fonts": N_("Download fonts for agent titles"),
    "agents_dictation_shortcut": N_("Dictation shortcut"),
    "agents_remote_enabled": N_("Agents from other computers"),
    "agents_raise_here": N_("Raise agent windows on this computer"),
    "agents_stale_minutes": N_("Stale after (minutes)"),
    "agents_forget_minutes": N_("Remove idle agents after (minutes)"),
}


# One sentence or two per setting, shown as the tooltip on its label and its
# editor. tests/gui/settings_dialog_test.py fails on a DEFAULT_SETTINGS key
# missing here, so a new setting cannot ship without one.
SETTING_DESCRIPTIONS = {
    kbd.BRIGHTNESS: N_(
        "Sets the brightness of the keycaps when you click OK. A level stays until you "
        "choose Automatic, which follows the daylight when Follow daylight is on, and "
        "otherwise returns to the keyboard's own stored level. The keyboard does not "
        "report its level, so no picture is selected when this dialog opens."),
    kbd.IDLE_STYLE: N_(
        "What the keycaps show when you have not typed for a while. A moving picture "
        "protects the displays from burn-in."),
    kbd.IDLE_TIMEOUT: N_("How long the keyboard waits before the idle display starts."),
    kbd.GLYPH_SCRIPT: N_(
        "Draws the letters and digits on the keycaps in another script, for example "
        "runes or a retro computer font. The keys still type the same characters. "
        "Standard shows the normal legends of your language."),
    kbd.GLYPH_PLACEMENT: N_(
        "Where the script's letters sit on the keycap. The top-left corner leaves room "
        "for an app icon."),
    kbd.GLYPH_SIZE: N_(
        "The size of the large letter or digit in the middle of each keycap. Medium "
        "and Large apply to Latin letters and digits; other scripts, such as Arabic "
        "or Chinese, stay Small."),
    kbd.TAPPING_TERM: N_(
        "A key with a tap and a hold action types its tap action when you release it "
        "before this time, and acts as its hold action when you hold it longer."),
    kbd.FLOW_TAP_TERM: N_(
        "A tap-hold key pressed within this time after the previous key always types its "
        "tap action, so fast typing does not trigger a modifier. 0 turns Flow Tap off."),
    kbd.AUTO_SHIFT: N_(
        "With Auto Shift on, holding a letter, digit or symbol key longer than the "
        "Auto Shift timeout types its shifted character."),
    kbd.AUTO_SHIFT_MS: N_("How long you hold a key before Auto Shift types its shifted "
                          "character."),
    "agents_enabled": N_(
        "Shows the state of AI coding agents on the number row and, while the AI key "
        "is pressed, one card per agent. Needs keyboard firmware with protocol 31. "
        "Takes effect at the next keyboard connect."),
    "agents_title_scan": N_(
        "Also finds agents that run in a terminal from the window title, without a "
        "hook. Not on macOS."),
    "agents_download_fonts": N_(
        "Downloads a font the first time an agent title needs one: Chinese, Hindi, "
        "Thai, Armenian, Hebrew or Arabic. The fonts come from GitHub and "
        "www.polykybd.org. Off: nothing is downloaded; fonts downloaded before are "
        "still used, and a title in a script without a font shows boxes."),
    "agents_remote_enabled": N_(
        "Also shows agents that run on a computer with the forwarder. A key press "
        "brings forward the remote-desktop viewer that shows that computer "
        "(NoMachine, Remote Desktop, VNC). They report over the network endpoint for "
        "forwarders, which must be on too. Off: only this computer's agents."),
    "agents_raise_here": N_(
        "On a computer with the forwarder: a key press on one of this computer's "
        "agents also brings the agent's own window forward here. Off: only the "
        "viewer on the keyboard's computer comes forward."),
    "agents_stale_minutes": N_(
        "A working agent that reports nothing for this many minutes shows as stale "
        "(dim white). 0: never."),
    "agents_forget_minutes": N_(
        "An idle or stale agent that reports nothing for this many minutes is removed "
        "and frees its key. An agent whose process ends is removed at once. 0: never."),
    "agents_dictation_shortcut": N_(
        "The shortcut the minus key sends in AI mode to start dictation, for example "
        "<cmd>+h or <ctrl>+<alt>+d. Empty: Win+H on Windows, nothing on macOS and "
        "Linux."),
    "unicode_send_composition_mode": N_(
        "Tells the keyboard which Unicode input method this computer uses (for "
        "example WinCompose on Windows), when it connects and whenever the method "
        "changes. The keyboard needs it to type characters that are not on your "
        "layout, such as emoji. Off: the keyboard keeps the method it has stored."),
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
    "irradiance_min": N_(
        "The sunlight value at which the keycaps are at their dimmest. Less sunlight "
        "keeps them at the dimmest level."),
    "irradiance_max": N_(
        "The sunlight value at which the keycaps are at their brightest. Lower it to "
        "reach full brightness on a cloudy day."),
    "irradiance_prescaler": N_(
        "Multiplies the sunlight value before it is compared with Sunlight at dimmest "
        "and Sunlight at brightest. Below 1 makes the keycaps dimmer for the same "
        "daylight."),
    "brightness_gamma": N_(
        "Shapes the daylight curve. Above 1 the middle of the day gets dimmer, "
        "below 1 brighter. The dimmest and brightest levels do not change."),
    "generic_overlays_enabled": N_(
        "Draws icons for apps that have no overlay of their own: the app's logo on "
        "the Escape key and an icon on each shortcut key. Off: these apps get no "
        "icons. Apps with their own overlay are not affected."),
    "generic_overlays_fill_gaps": N_(
        "An app with its own overlay also gets its logo on the Escape key, when its "
        "overlay leaves Escape blank."),
    "generic_overlays_fill_shortcuts": N_(
        "An app with its own overlay also gets icons for the shortcuts listed in its "
        "menus, on the keys its overlay leaves blank. Reading the menus of a large "
        "app, such as a browser with a long page, can take minutes."),
    "shortcut_icons_enabled": N_(
        "Reads the shortcuts listed in the focused app's menus, through the "
        "accessibility interface of the operating system, and draws an icon on each "
        "shortcut key. The shortcuts stay on this computer. Off: no app is read."),
    "shortcut_icon_auto_fetch": N_(
        "Downloads app logos and shortcut icons that this computer does not have yet "
        "from the internet (simple-icons and Iconify). They are stored on this "
        "computer. Off: icons already downloaded keep working, and an app without a "
        "stored icon gets none."),
    "shortcut_enable_accessibility": N_(
        "Linux only. Turns on the desktop's accessibility switch, so Qt and KDE apps "
        "list their shortcuts for Read shortcuts from app menus. Off: only apps that "
        "list them anyway (GTK) are read."),
    "max_hid_message_before_delay": N_(
        "USB transport: how many image messages are sent before a short pause, so "
        "the keyboard keeps reacting to typing. Change it only when asked to while "
        "reporting a problem."),
    "delay_time_after_max_hid_messages": N_(
        "USB transport: the length of that pause, in seconds. Change it only when "
        "asked to while reporting a problem."),
    "hid_reconnect_retries": N_(
        "How many times the app asks the keyboard for its ID without an answer before "
        "it closes and reopens the USB connection. Change it only when asked to while "
        "reporting a problem."),
    "ui_theme": N_(
        "The look of the tray menu and dialogs. Automatic follows the desktop's "
        "light or dark setting."),
    "ui_language": N_(
        "The language of the menus and dialogs. Applies when the tray app restarts."),
    "developer_mode": N_(
        "Shows the developer settings in this dialog, and the Developer submenu in "
        "the tray menu after a restart."),
    "log_detail": N_(
        "How much the app writes to its log. Debug and Detailed help when you report "
        "a problem, and make the log grow faster. Applies after a restart."),
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
        "Accepts reports of the focused window from the forwarder app on another "
        "computer, for example one you use through remote desktop, so the keyboard "
        "shows the icons of that computer's apps. Opens a network port. Applies after "
        "a restart."),
    "emoji_search_dict": N_(
        "The language of the words the keyboard's emoji search matches. The "
        "dictionary is sent to the keyboard when you click OK, and when it connects "
        "if Send font packs on connect is on. Own dictionary file, when set, is used "
        "instead."),
    "emoji_search_dict_file": N_(
        "A dictionary file you built yourself (.plyd), sent to the keyboard instead "
        "of the Search language dictionary. Empty: the dictionary for the Search "
        "language is used."),
    "fontpack_auto_flash": N_(
        "When the keyboard connects, sends it the font packs it is missing or has in "
        "an older version. Font packs hold the characters for languages, symbols and "
        "emoji."),
    "fontpack_path": N_(
        "A font-pack file (.plyf) to send to the keyboard instead of the one that "
        "comes with this app. Empty: the font pack that comes with this app is used."),
    "browser_url_detection": N_(
        "Chooses a website's overlay from the address of the focused browser tab. The "
        "address comes from the PolyKybd browser extension; on macOS, Safari and "
        "Chromium browsers such as Chrome also give it without the extension. Off: a "
        "website's overlay is chosen from the window title only."),
    "browser_report_local_enabled": N_(
        "Runs the receiver that the PolyKybd browser extension sends the address of "
        "the focused tab to. It accepts connections from this computer only "
        "(127.0.0.1)."),
    "browser_report_port": N_(
        "The receiver's port. It must match the Host port in the browser extension."),
    "browser_report_token": N_(
        "A shared secret. When set, the browser extension must send the same token."),
    "telemetry_enabled": N_(
        "Sends one anonymous usage report per day: versions, operating system and a "
        "few counters. Never window titles or app names."),
    "telemetry_endpoint": N_(
        "The web address the usage report is sent to. Empty: no report is sent."),
    "telemetry_install_id": N_(
        "The random ID of this installation, created with the first report. Delete "
        "it to count as a new installation."),
    "problem_scan_keyboard_console": N_(
        "Watches the messages the keyboard sends over USB for known failures, and "
        "offers to report a problem."),
    "problem_scan_host_logs": N_(
        "Watches this app's own log for known failure messages, and offers to report "
        "a problem."),
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
SIDEBAR_WIDTH = 210


def setting_tooltip(full_key):
    """The translated description as rich text, so Qt wraps it, or ""."""
    text = SETTING_DESCRIPTIONS.get(full_key)
    return f"<p>{html.escape(_(text))}</p>" if text else ""


def setting_description(full_key):
    """The translated description as plain text, or ""."""
    text = SETTING_DESCRIPTIONS.get(full_key)
    return _(text) if text else ""


def minimum_dialog_size(available):
    """`MIN_DIALOG_SIZE` at the display's scale, but never more than 90 % of the
    available screen: at 150 % the scaled minimum is 960 x 720, taller than a
    1366 x 768 laptop screen leaves, and the OK and Cancel row went off screen."""
    return QSize(min(px(MIN_DIALOG_SIZE.width()), available.width() * 9 // 10),
                 min(px(MIN_DIALOG_SIZE.height()), available.height() * 9 // 10))


def initial_dialog_size(available, minimum=MIN_DIALOG_SIZE):
    """Half the available screen area, never below `minimum`."""
    return QSize(max(minimum.width(), available.width() // 2),
                 max(minimum.height(), available.height() // 2))


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


def layout_sections(keys):
    """Place `keys` into the dialog's sections.

    Returns ``[(section_id, title, [(subheading, [key, ...]), ...]), ...]`` in
    sidebar order, with empty groups and sections left out. Keys no section
    names go to "Other", last. Which ``dev_`` rows are shown is decided by the
    dialog (:meth:`SettingsDialog._update_developer_rows`), not here.
    """
    keys = list(keys)
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
        # The colour of the track when on: its section's colour
        # (gui/section_colors.py), or the palette highlight when None.
        self.accent = None
        # The knob's colour when on; white when None.
        self.knob = None

    def set_accent(self, color):
        self.accent = QColor(color) if color else None
        self.update()

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
        left = self.width() - 2 - self.TRACK.width() if self.isRightToLeft() else 2
        track = QRectF(left, (self.height() - self.TRACK.height()) / 2,
                       self.TRACK.width(), self.TRACK.height())
        radius = track.height() / 2
        if not self.isEnabled():
            fill = pal.color(QPalette.Disabled, QPalette.Mid)
        elif self.isChecked():
            fill = self.accent or pal.color(QPalette.Highlight)
        else:
            fill = pal.color(QPalette.Mid)
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(track, radius, radius)
        knob_d = track.height() - 6
        # "On" is the reading direction's end: right, or left in Arabic and Persian.
        on_right = not self.isRightToLeft()
        at_end = self.isChecked() == on_right
        x = track.right() - 3 - knob_d if at_end else track.left() + 3
        painter.setBrush(QColor(self.knob if self.isChecked() and self.knob else "#ffffff"))
        painter.drawEllipse(QRectF(x, track.top() + 3, knob_d, knob_d))
        if self.hasFocus():
            ring = QPen(self.accent or pal.color(QPalette.Highlight))
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
        combo.setMinimumWidth(px(160))
        combo.setMaximumWidth(px(260))
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
        spinbox.setFixedWidth(px(120))
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
        doublebox.setFixedWidth(px(120))
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
QLabel#settingsRowNote { color: palette(text); font-style: italic; }
QListWidget#settingsNav {
    background: transparent;
    border: none;
    outline: none;
}
"""


class _SearchField(QLineEdit):
    """The search field. Enter does nothing, rather than pressing OK."""

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            event.accept()
            return
        super().keyPressEvent(event)


# How far the description text moves from the text colour toward the card's
# background (Base), so the setting's name stands out above it.
_DESCRIPTION_FADE = 0.40


def _description_color(palette):
    text = palette.color(QPalette.Active, QPalette.WindowText)
    base = palette.color(QPalette.Active, QPalette.Base)
    f = _DESCRIPTION_FADE
    return QColor(round(text.red() + (base.red() - text.red()) * f),
                  round(text.green() + (base.green() - text.green()) * f),
                  round(text.blue() + (base.blue() - text.blue()) * f))


class _SettingRow(QWidget):
    """One setting: its label, the description below it, and its control.

    A short control (switch, number, list) sits on the right of the text. A
    text field takes the full row width below the text, because a path or a
    URL squeezed beside a description is unreadable.
    """

    def __init__(self, full_key, editor, extra=None, note="", parent=None):
        super().__init__(parent)
        self.full_key = full_key
        self.editor = editor
        # False hides the row whatever the search says (a developer setting
        # while developer mode is off and the setting is at its default).
        self.available = True
        self.advanced = full_key in ADVANCED_SETTINGS
        title = setting_label(full_key)
        description = setting_description(full_key)
        self.search_words = search_words(f"{title} {description} {full_key}")

        title_lbl = QLabel(title)
        title_lbl.setWordWrap(True)
        title_lbl.setObjectName("settingsTitle")
        # The name stands out from the longer description below it: semibold
        # and a little larger.
        title_font = title_lbl.font()
        title_font.setWeight(QFont.DemiBold)
        title_font.setPointSizeF(title_font.pointSizeF() * 1.06)
        title_lbl.setFont(title_font)
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
            muted.setColor(QPalette.WindowText, _description_color(muted))
            desc_lbl.setPalette(muted)
            text_col.addWidget(desc_lbl)
        if note:
            note_lbl = QLabel(note)
            note_lbl.setWordWrap(True)
            note_lbl.setObjectName("settingsRowNote")
            text_col.addWidget(note_lbl)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(6)
        if isinstance(editor, QLineEdit) or editor.property("wideEditor"):
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
        return self.available and search_matches(query, self.search_words)


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

    def apply_filter(self, query, show_advanced=True):
        """Show the matching rows; a subheading match shows the whole group.
        Without ``show_advanced`` and without a search, the advanced rows are
        hidden."""
        whole = bool(query) and search_matches(query, search_words(self.subheading))
        shown = [r for r in self.rows if r.available and (whole or r.matches(query))
                 and (show_advanced or query or not r.advanced)]
        for r in self.rows:
            r.setVisible(r in shown)
        # A divider sits above every row but the first; show one only between
        # two visible rows.
        seen = self.rows[0] in shown
        for line, r in zip(self._dividers, self.rows[1:]):
            line.setVisible(seen and r in shown)
            seen = seen or r in shown
        self.setVisible(bool(shown))
        return bool(shown)


class _Section(ColorSection):
    """A Settings section: a ColorSection (gui/section_style.py) holding a note
    and the groups of rows."""

    def __init__(self, section_id, title, color=None, parent=None):
        super().__init__(_(title), color, parent)
        self.section_id = section_id
        self.groups = []
        self._lay = self.body_layout
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setObjectName("settingsRowNote")
        self.note.hide()
        self._lay.addWidget(self.note)

    def set_note(self, text):
        self.note.setText(text)
        self.note.setVisible(bool(text))

    def add_group(self, group):
        self.groups.append(group)
        self._lay.addWidget(group)

    def add_advanced_switch(self, on, on_toggled):
        """Put the Advanced switch in the title band, when a row is advanced."""
        if not any(r.advanced for g in self.groups for r in g.rows):
            return
        label = QLabel(_("Advanced"))
        label.setObjectName("sectionAdvancedLabel")
        if self.color:
            label.setStyleSheet(f"color: {section_colors.title_ink(self.color)}; "
                                "font-size: 10pt; font-weight: normal; "
                                "background: transparent; padding: 0;")
        self.advanced_switch = ToggleSwitch()
        self.advanced_switch.setChecked(on)
        self.advanced_switch.setToolTip(_(
            "Shows the settings that most people never change."))
        if self.color:
            # The section colour on a band of the same colour would vanish;
            # the title ink keeps the switch visible.
            # The knob takes the section colour, so a white track (the light
            # theme's ink) still shows it.
            self.advanced_switch.set_accent(section_colors.title_ink(self.color))
            self.advanced_switch.knob = QColor(self.color)
        label.setBuddy(self.advanced_switch)
        self.head_layout.addWidget(label)
        self.head_layout.addWidget(self.advanced_switch)
        self.advanced_switch.toggled.connect(on_toggled)

    @property
    def show_advanced(self):
        switch = getattr(self, "advanced_switch", None)
        return switch is None or switch.isChecked()

    def apply_filter(self, query):
        visible = [g.apply_filter(query, self.show_advanced) for g in self.groups]
        self.setVisible(any(visible))
        return any(visible)


class SettingsDialog(QDialog):
    # The sections whose Advanced switch is on, kept while the app runs, so
    # the next Settings window opens the same way.
    advanced_sections = set()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("PolyKybd Settings"))
        self.edit_widgets = {}
        self._all_settings = {}
        self._sections = []
        self._rows = {}
        self._syncing_nav = False
        self._developer_mode = False
        self._flag_source = None
        # Settings > Keyboard: the editors of the values stored on the keyboard,
        # by pseudo key, and the values read from it (gui/keyboard_settings.py).
        self.keyboard_widgets = {}
        self._keyboard_read = {}
        self._keyboard_section = None

    def sizeHint(self):
        return MIN_DIALOG_SIZE

    def _fit_to_screen(self):
        """Open at half the screen the cursor is on, with the old size as minimum."""
        screen = (QGuiApplication.screenAt(QCursor.pos())
                  or QGuiApplication.primaryScreen())
        if screen is None:
            self.setMinimumSize(px(MIN_DIALOG_SIZE.width()), px(MIN_DIALOG_SIZE.height()))
            return
        available = screen.availableGeometry().size()
        minimum = minimum_dialog_size(available)
        self.setMinimumSize(minimum)
        self.resize(initial_dialog_size(available, minimum))

    def setup(self, settings_dict, developer_mode=False, flag_source=None, keyboard=False):
        """Build the dialog for `settings_dict`.

        `developer_mode` is whether this run is in developer mode. `flag_source`
        names the command-line flag ("--dev") that decided developer mode and the
        log detail for this run, or None when the settings did. `keyboard` adds
        the rows of the settings stored on the keyboard (the tray app; the
        forwarder has no keyboard). They stay disabled until
        :meth:`set_keyboard_reads` gives them the keyboard's values.
        """
        self._all_settings = dict(settings_dict)
        self._developer_mode = bool(developer_mode)
        self._flag_source = flag_source
        # No setWindowIcon here: the dialog inherits QApplication's, which
        # IconStateManager already sets to the right mark for whichever app
        # opened it (the P for the tray app, the F for the forwarder). Pinning
        # pcolor.png put the tray app's mark on the forwarder's Settings window.
        self.setStyleSheet(_STYLE)
        keys = list(settings_dict)
        dark = is_dark(self.palette())
        if keyboard:
            keys += list(kbd.KEYS)
        layout = layout_sections(keys)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        main.addLayout(body, 1)

        # Sidebar: the search field and the section list.
        side = QWidget()
        side.setFixedWidth(px(SIDEBAR_WIDTH))
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
        section_style.style_nav(self.nav)
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
        # The column takes the whole width of the window. Each row keeps its
        # control beside its own label and description, so a wide window
        # widens the description rather than parting the control from it.
        column = QWidget()
        col_lay = QVBoxLayout(column)
        col_lay.setContentsMargins(0, 0, 0, 0)
        col_lay.setSpacing(28)
        holder_lay.addWidget(column, 1)

        for section_id, title, groups in layout:
            section = _Section(section_id, title,
                               section_colors.section_color(section_id, dark))
            for subheading, keys in groups:
                group = _Group(subheading)
                for full_key in keys:
                    if full_key in kbd.KEYS:
                        group.add_row(self._make_keyboard_row(full_key))
                    else:
                        group.add_row(self._make_row(full_key, settings_dict[full_key]))
                section.add_group(group)
            # On/off switches take the section's colour, like its band.
            for group in section.groups:
                for row in group.rows:
                    if isinstance(row.editor, ToggleSwitch):
                        row.editor.set_accent(section.color)
            section.add_advanced_switch(
                section_id in SettingsDialog.advanced_sections,
                lambda on, sid=section_id: self._advanced_toggled(sid, on))
            if section_id == "icons":
                section.set_note(_("An overlay is a set of icons for one app. Help & "
                                   "About, Basics shows an example."))
            if section_id == "keyboard" and keyboard:
                self._keyboard_section = section
                section.set_note(_("Reading the settings stored on the keyboard\u2026"))
            col_lay.addWidget(section)
            self._sections.append(section)
            section_style.add_nav_item(self.nav, section.title, section.color)
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
        style_button_box(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        main.addLayout(footer)

        switch = self.edit_widgets.get("developer_mode")
        if isinstance(switch, QCheckBox):
            switch.toggled.connect(lambda _on: self._refilter())
        self._refilter()
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
        elif full_key == "browser_report_token" and isinstance(editor, QLineEdit):
            extra = self._token_button(editor)
        self.edit_widgets[full_key] = editor
        note = ""
        if self._flag_source and full_key in ("developer_mode", "log_detail"):
            note = _f("Set by {flag} for this run. This setting applies when the app "
                      "starts without it.", flag=self._flag_source)
        row = _SettingRow(full_key, editor, extra, note)
        self._rows[full_key] = row
        return row

    def _make_keyboard_row(self, key):
        """A row for a value stored on the keyboard. Disabled until read."""
        editor = self._keyboard_editor(key)
        editor.setAccessibleName(setting_label(key))
        tooltip = setting_tooltip(key)
        if tooltip and not isinstance(editor, kbd.TileChoice):
            editor.setToolTip(tooltip)
        editor.setEnabled(False)
        self.keyboard_widgets[key] = editor
        row = _SettingRow(key, editor)
        self._rows[key] = row
        return row

    @staticmethod
    def _keyboard_editor(key):
        if key == kbd.BRIGHTNESS:
            return kbd.make_brightness_editor()
        if key == kbd.IDLE_STYLE:
            return kbd.make_idle_style_editor()
        if key == kbd.GLYPH_SCRIPT:
            return kbd.make_glyph_script_editor()
        if key == kbd.GLYPH_SIZE:
            return kbd.make_glyph_size_editor()
        if key in (kbd.IDLE_TIMEOUT, kbd.GLYPH_PLACEMENT):
            combo = SettingComboBox()
            choices = (kbd.idle_timeout_choices() if key == kbd.IDLE_TIMEOUT
                       else kbd.glyph_placement_choices())
            for value, label in choices:
                combo.addItem(label, value)
            return combo
        if key == kbd.AUTO_SHIFT:
            return ToggleSwitch()
        spin = SettingSpinBox()
        lo, hi = {kbd.TAPPING_TERM: (TapTerms.TAPPING_MIN_MS, TapTerms.TAPPING_MAX_MS),
                  kbd.FLOW_TAP_TERM: (TapTerms.FLOW_TAP_MIN_MS, TapTerms.FLOW_TAP_MAX_MS),
                  kbd.AUTO_SHIFT_MS: (TapTerms.AUTO_SHIFT_MIN_MS,
                                      TapTerms.AUTO_SHIFT_MAX_MS)}[key]
        spin.setRange(lo, hi)
        spin.setSingleStep(TapTerms.STEP_MS)
        # TRANSLATORS: unit after a number of milliseconds in a spin box.
        spin.setSuffix(_(" ms"))
        if key == kbd.FLOW_TAP_TERM:
            # TRANSLATORS: shown in the Flow Tap spin box when its value is 0.
            spin.setSpecialValueText(_("Off"))
        # The step applies to the arrows only; snap a typed value when editing
        # ends, so what the user sees is what is sent.
        spin.editingFinished.connect(lambda b=spin: b.setValue(kbd.snap_ms(b.value())))
        return spin

    @staticmethod
    def _keyboard_value(editor):
        if isinstance(editor, kbd.TileChoice):
            return editor.value()
        if isinstance(editor, QComboBox):
            return editor.currentData()
        if isinstance(editor, QCheckBox):
            return editor.isChecked()
        return kbd.snap_ms(editor.value())

    def set_keyboard_reads(self, reads):
        """Fill the keyboard rows from :func:`keyboard_settings.read_all`'s answer
        (or the exception it raised) and enable the ones that were read."""
        if not self.keyboard_widgets:
            return
        if isinstance(reads, Exception):
            reads = {}
        values, failed = kbd.values_from_reads(reads or {})
        self._keyboard_read = dict(values)
        for key, editor in self.keyboard_widgets.items():
            if key in values:
                value = values[key]
                if isinstance(editor, kbd.TileChoice):
                    editor.set_value(value)
                elif isinstance(editor, QComboBox):
                    index = editor.findData(value)
                    if index < 0:
                        # A preset this host does not know: show it, keep it.
                        editor.addItem(str(value), value)
                        index = editor.count() - 1
                    editor.setCurrentIndex(index)
                elif isinstance(editor, QCheckBox):
                    editor.setChecked(bool(value))
                else:
                    editor.setValue(int(value))
                editor.setEnabled(True)
            else:
                editor.setEnabled(False)
                editor.setToolTip(_("This keyboard's firmware does not have this setting.")
                                  if key not in failed else
                                  _("Could not read this setting from the keyboard."))
        auto = self.keyboard_widgets.get(kbd.AUTO_SHIFT)
        auto_ms = self.keyboard_widgets.get(kbd.AUTO_SHIFT_MS)
        if auto is not None and auto_ms is not None and kbd.AUTO_SHIFT in values:
            auto_ms.setEnabled(auto.isChecked())
            auto.toggled.connect(auto_ms.setEnabled)
        if self._keyboard_section is not None:
            if not values:
                note = _("Connect the keyboard to change the settings stored on it.")
            elif failed:
                note = _("Some settings could not be read from the keyboard. Update the "
                         "keyboard firmware to change them here.")
            else:
                note = ""
            self._keyboard_section.set_note(note)

    def keyboard_changes(self):
        """{pseudo key: new value} for each keyboard row the user changed."""
        out = {}
        for key, before in self._keyboard_read.items():
            editor = self.keyboard_widgets.get(key)
            if editor is None:
                continue
            value = self._keyboard_value(editor)
            if value is not None and value != before:
                out[key] = value
        return out

    def _advanced_toggled(self, section_id, on):
        if on:
            SettingsDialog.advanced_sections.add(section_id)
        else:
            SettingsDialog.advanced_sections.discard(section_id)
        self._refilter()

    def _developer_settings_shown(self):
        """Whether the dialog shows every developer setting: the switch is on,
        or a flag put this run in developer mode."""
        switch = self.edit_widgets.get("developer_mode")
        on = switch.isChecked() if isinstance(switch, QCheckBox) else False
        return on or (self._flag_source is not None and self._developer_mode)

    def _update_developer_rows(self):
        """Show the dev_ rows for developer mode, and any that is not at its
        default otherwise.

        ⚠️ Every dev_ setting takes effect with developer mode off too. Hiding an
        active one (the plaintext relay, the simulated keyboard) left it running
        with no switch in sight to turn it off.
        """
        shown = self._developer_settings_shown()
        current = self.get_updated_settings()
        active = False
        for key, row in self._rows.items():
            if not key.startswith("dev_"):
                continue
            changed = key in DEFAULT_SETTINGS and current.get(key) != DEFAULT_SETTINGS[key]
            row.available = shown or changed
            active = active or (changed and not shown)
        for section in self._sections:
            if section.section_id == "developer":
                section.set_note(_("These developer settings are not at their default, "
                                   "so they stay in effect while developer mode is "
                                   "off.") if active else "")

    def _nav_selected(self, row):
        if self._syncing_nav or not 0 <= row < len(self._sections):
            return
        section = self._sections[row]
        if section.isVisible():
            # A few pixels above the section, so its colour band shows. The
            # jump keeps the entry the user clicked: a short section would
            # otherwise hand the selection to the one below it (_sync_nav).
            self._syncing_nav = True
            try:
                self.scroll.verticalScrollBar().setValue(section.parentWidget().mapTo(
                    self.scroll.widget(), section.pos()).y() - px(8))
            finally:
                self._syncing_nav = False

    def _sync_nav(self, value):
        """Select the section the reader is in as the page scrolls. A section
        counts once its top is in the upper third of the view, so the sidebar
        moves on while the next section's title band comes into view, not
        only when it reaches the top edge."""
        if self._syncing_nav:
            return
        current = 0
        holder = self.scroll.widget()
        reach = value + max(px(40), self.scroll.viewport().height() // 3)
        for i, section in enumerate(self._sections):
            if not section.isVisible():
                continue
            top = section.parentWidget().mapTo(holder, section.pos()).y()
            if top <= reach:
                current = i
        bar = self.scroll.verticalScrollBar()
        if value >= bar.maximum() and bar.maximum() > 0:
            visible = [i for i, s in enumerate(self._sections) if s.isVisible()]
            current = visible[-1] if visible else current
        self._syncing_nav = True
        self.nav.setCurrentRow(current)
        self._syncing_nav = False

    def _apply_filter(self, _text):
        """A new search: filter, then start at the top of the results."""
        self._refilter()
        self.scroll.verticalScrollBar().setValue(0)

    def _refilter(self):
        """Show the rows that are available and match the search."""
        self._update_developer_rows()
        query = self.search.text().strip().casefold()
        any_shown = False
        for i, section in enumerate(self._sections):
            shown = section.apply_filter(query)
            any_shown = any_shown or shown
            self.nav.item(i).setHidden(not shown)
        self._no_match.setVisible(not any_shown)

    def _browse_button(self, full_key, line_edit):
        button = QToolButton()
        button.setText("…")
        button.setToolTip(_("Browse…"))
        button.setAccessibleName(_("Browse…"))
        button.clicked.connect(lambda: self._browse_folder(full_key, line_edit))
        return button

    def _token_button(self, line_edit):
        """Fill in a new random token and copy it: the extension's Options take
        the same one."""
        button = set_button_icon(QPushButton(_("Generate")), "reload")
        button.setToolTip(_("Fills in a new random token and copies it. Paste it into "
                            "the browser extension's Options and save both."))

        def generate():
            import secrets
            token = secrets.token_urlsafe(24)
            line_edit.setText(token)
            QApplication.clipboard().setText(token)
        # noinspection PyUnresolvedReferences
        button.clicked.connect(generate)
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
