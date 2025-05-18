import logging
import os
import pathlib
import platform
import sys
import traceback
import webbrowser
import yaml

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QAction,
    QDialog,
    QMessageBox,
    QFileDialog,
)

from polyhost.gui.settings_dialog import SettingsDialog
from polyhost.cmd_menu import CommandsSubMenu
from polyhost.handler.active_window import OverlayHandler
from polyhost.handler.common import OverlayCommand
from polyhost.input.linux_gnome_helper import LinuxGnomeInputHelper
from polyhost.input.linux_kde_helper import LinuxPlasmaHelper
from polyhost.input.macos_helper import MacOSInputHelper
from polyhost.input.win_helper import WindowsInputHelper
from polyhost.settings import PolySettings
from polyhost.device.poly_kybd_cmds import PolyKybd
from polyhost._version import __version__

from polyhost.input.unicode_input import get_input_method
from polyhost.services.sunlight_helper import Sunlight

IS_PLASMA = os.getenv("XDG_CURRENT_DESKTOP") == "KDE"

UPDATE_CYCLE_MSEC = 250
RECONNECT_CYCLE_MSEC = 1000
PERIODIC_10MIN_CYCLE_MSEC = 1000*60*10
NEW_WINDOW_ACCEPT_TIME_MSEC = 1000

def sort_by_country_abc(item):
    return item[2:]


def get_overlay_path(filepath):
    return os.path.join(os.path.dirname(__file__), "res", "overlays", filepath)


# noinspection PyUnresolvedReferences
class PolyHost(QApplication):
    def __init__(self, log_level):
        super().__init__(sys.argv)

        logging.basicConfig(
            level=log_level,
            format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(filename='host_log.txt'), logging.StreamHandler(stream=sys.stdout)]
        )
        self.log = logging.getLogger('PolyHost')
        self.setApplicationName('PolyHost')
        self.settings = PolySettings()

        self.setQuitOnLastWindowClosed(False)
        self.is_closing = False

        # Create the icon
        icon = QIcon(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/icons/pcolor.png"))

        # Create the tray
        self.tray = QSystemTrayIcon(parent=self)
        self.tray.setIcon(icon)
        self.tray.setVisible(True)
        self.tray.setToolTip(f"PolyKybdHost {__version__}")

        # Create the menu
        self.menu = QMenu()
        self.menu.setStyleSheet("QMenu {icon-size: 64px;} QMenu::item {icon-size: 64px; background: transparent;}")

        #self.keeb = PolyKybdMock(f"{__version__}")
        self.kb_sw_version = None
        self.keeb = PolyKybd()
        self.connected = False
        self.paused = False
        self.status = QAction(QIcon(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/icons/sync.svg")), "Waiting for PolyKybd...", parent=self)
        self.status.setToolTip("Press to pause connection")
        self.status.triggered.connect(self.pause)
        self.exit = QAction(QIcon(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/icons/power.svg")), "Quit", parent=self)
        self.exit.triggered.connect(self.quit_app)
        self.support = QAction(QIcon(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/icons/support.svg")), "Get Support", parent=self)
        self.support.triggered.connect(self.open_support)
        self.about = QAction(QIcon(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/icons/home.svg")), "About", parent=self)
        self.about.triggered.connect(self.open_about)

        self.last_update_msec = 0
        self.last_update_10min_task = PERIODIC_10MIN_CYCLE_MSEC * 2
        self.current_lang = None
        self.keeb_lang_menu = None

        self.reconnect()
        self.menu.addAction(self.status)
        self.add_supported_lang(self.menu)

        lang_menu = self.menu.addMenu(QIcon(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/icons/language.svg")), "Change System Input Language")

        self.cmdMenu = CommandsSubMenu(self, self.keeb)
        self.cmdMenu.build_menu(self.menu)

        action = QAction(QIcon(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/icons/overlays.svg")), "Send Shortcut Overlay...", parent=self)
        action.triggered.connect(self.send_shortcuts)
        self.menu.addAction(action)

        action = QAction(QIcon(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/icons/via.png")), "Configure Keymap (VIA)", parent=self)
        action.triggered.connect(self.open_via)
        self.menu.addAction(action)

        action = QAction(QIcon(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/icons/settings.svg")), "Settings", parent=self)
        action.triggered.connect(self.open_settings)
        self.menu.addAction(action)

        self.menu.addAction(self.support)
        self.menu.addAction(self.about)
        self.menu.addAction(self.exit)

        self.helper = None
        if platform.system() == "Windows":
            self.helper = WindowsInputHelper()
        elif platform.system() == "Linux":
            if IS_PLASMA:
                self.helper = LinuxPlasmaHelper()
            else:
                self.helper = LinuxGnomeInputHelper()
        elif platform.system() == "Darwin":
            self.helper = MacOSInputHelper()

        entries = self.helper.get_languages()

        result = self.helper.get_current_language()
        if result:
            success, sys_lang = result
            if success:
                self.log.info(f"Current System Language: {sys_lang}")
                self.current_lang = sys_lang
            else:
                self.log.warning("Could not query current System Language.")
        else:
            self.log.warning("System language query not supported for this platform.")

        for e in entries:
            self.log.info(f"Enumerating input language {e}")
            lang_menu.addAction(e, self.change_system_language)

        self.managed_connection_status()
        # Add the menu to the tray
        #self.tray.activated.connect(self.on_activated)
        self.tray.setContextMenu(self.menu)
        self.tray.show()

        self.mapping = {}
        self.read_overlay_mapping_file(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/overlays/overlay-mapping.poly.yaml"))

        self.overlay_handler = OverlayHandler(self.mapping)

        self.setStyle("Fusion")
        # Now use a palette to switch to dark colors:
        palette = QPalette()
        base_color = QColor(35, 35, 35)
        window_base_color = QColor(99, 99, 99)
        text_color = QColor(150, 150, 150)
        highlight_text_color = QColor(255, 255, 255)
        palette.setColor(QPalette.Window, window_base_color)
        palette.setColor(QPalette.WindowText, text_color)
        palette.setColor(QPalette.Base, base_color)
        palette.setColor(QPalette.AlternateBase, window_base_color)
        palette.setColor(QPalette.ToolTipBase, base_color)
        palette.setColor(QPalette.ToolTipText, text_color)
        palette.setColor(QPalette.Text,text_color)
        palette.setColor(QPalette.Button, window_base_color)
        palette.setColor(QPalette.ButtonText, text_color)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, highlight_text_color)
        self.setPalette(palette)

        self.sunlight = Sunlight(self.settings.get("allow_online_request_for_brightness"))
        QTimer.singleShot(UPDATE_CYCLE_MSEC * 2, self.active_window_reporter)

    # def on_activated(self, i_reason):
    #     if i_reason == QSystemTrayIcon.Trigger:
    #         if not self.menu.isVisible():
    #             self.menu.popup(QCursor.pos())
    #         else:
    #             self.menu.hide()

    def managed_connection_status(self):
        for action in self.menu.actions():
            action.setEnabled(self.connected and not self.paused)
        self.status.setEnabled(True)
        self.support.setEnabled(True)
        self.about.setEnabled(True)
        self.exit.setEnabled(True)

    def show_mb(self, title, msg, result=False):
        if not result:
            if self.connected:
                mbox = QMessageBox()
                mbox.setWindowTitle(title)
                mbox.setText(msg)
                mbox.setIcon(QMessageBox.Warning if title == "Error" else QMessageBox.Information)
                mbox.exec_()
            else:
                self.log.warning(f"{title}: {msg}")

    def pause(self):
        self.paused = not self.paused
        if self.paused:
            self.status.setText("Reconnect")
            self.connected = False
            self.status.setToolTip("")
        else:
            self.status.setToolTip("Press to pause connection")
        self.managed_connection_status()

    def reconnect(self):
        if not self.paused:
            result = False
            lang = ""
            if self.keeb.connect():
                result, lang = self.keeb.query_current_lang()

            if result != self.connected:
                self.connected, msg = self.keeb.query_version_info()
                if self.connected:
                    kb_version = self.keeb.get_sw_version()
                    self.kb_sw_version = self.keeb.get_sw_version_number()
                    expected = __version__
                    if kb_version.startswith(expected[:3]):
                        if kb_version != expected:
                            self.log.warning(f"Warning! Minor version mismatch, expected {expected}, got {kb_version}'.")
                            self.status.setIcon(QIcon(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/icons/sync_problem.svg")))
                            self.status.setText(
                                f"PolyKybd {self.keeb.get_name()} {self.keeb.get_hw_version()} ({kb_version}, please update to {expected}!)")
                        else:
                            self.status.setIcon(QIcon(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/icons/sync.svg")))
                            self.status.setText(
                                f"PolyKybd {self.keeb.get_name()} {self.keeb.get_hw_version()} ({kb_version})")
                        if result and self.settings.get("send_unicode_mode_to_kb"):
                            mode = get_input_method()
                            self.log.info("Setting unicode mode to %s", str(mode))
                            self.keeb.set_unicode_mode(mode.value)
                            self.update_ui_on_lang_change(lang)
                    else:
                        self.status.setIcon(QIcon(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/icons/sync_disabled.svg")))
                        self.status.setText(f"Incompatible version: {msg}, expected {expected}, got {kb_version}'.")
                        self.connected = False
                else:
                    self.status.setIcon(QIcon(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/icons/sync_disabled.svg")))
                    self.status.setText(msg)
            self.managed_connection_status()
            return lang
        return self.current_lang

    @staticmethod
    def langcode_to_flag(lang_code):
        result = ""
        for ch in lang_code:
            num = 0x1F1E6 + ord(ch.upper()) - ord('A')
            result = f"{result}{chr(num)}"
        return result

    def add_supported_lang(self, menu):
        result, _ = self.keeb.enumerate_lang()
        if result:
            self.current_lang = self.keeb.get_current_lang()
            self.keeb_lang_menu = menu.addMenu(f"Selected Language: {self.current_lang[:2]} {self.langcode_to_flag(self.current_lang[2:])}")

            all_languages = sorted(self.keeb.get_lang_list(), key=sort_by_country_abc)
            for lang in all_languages:
                text = f"{lang[:2]} {self.langcode_to_flag(lang[2:])}"
                if lang == self.current_lang:
                    text = f"{text} {chr(0x2714)}"
                item = self.keeb_lang_menu.addAction(text, self.change_keeb_language)
                item.setData(lang)

    def update_ui_on_lang_change(self, new_lang):
        if self.keeb_lang_menu:
            self.keeb_lang_menu.setTitle(f"Selected Language: {new_lang[:2]} {self.langcode_to_flag(new_lang[2:])}")
            for action in self.keeb_lang_menu.actions():
                lang = action.data()
                text = f"{lang[:2]} {self.langcode_to_flag(lang[2:])}"
                if lang == new_lang:
                    text = f"{text} {chr(0x2714)}"
                action.setText(text)

    @staticmethod
    def open_via():
        webbrowser.open("https://usevia.app", new=0, autoraise=True)

    def open_settings(self):
        dlg = SettingsDialog()
        dlg.setup(self.settings.get_all())
        if dlg.exec_() == QDialog.Accepted:
            self.settings.set_all(dlg.get_updated_settings())
        dlg.close()

    @staticmethod
    def open_support():
        webbrowser.open("https://discord.gg/5eU48M79", new=0, autoraise=True)

    @staticmethod
    def open_about():
        webbrowser.open("https://ko-fi.com/polykb", new=0, autoraise=True)

    def send_shortcuts(self):
        file_name = QFileDialog.getOpenFileName(None, 'Open file', '', "Image files (*.jpg *.gif *.png *.bmp *.jpeg)")
        if len(file_name) > 0:
            self.keeb.send_overlays(file_name[0], self.kb_sw_version[1]>=5 and self.kb_sw_version[2] >=4)
        else:
            self.log.info("No file selected. Operation canceled.")

    def change_system_language(self):
        lang = self.sender().text()
        result, output = self.helper.set_language(lang)
        if not result:
            self.show_mb("Error", f"Changing input language to '{lang}' failed with:\n\"{output}\"")
        else:
            self.log.info(f"Change input language to '{lang}'.")

    def change_keeb_language(self):
        lang = self.sender().data()
        result, msg = self.keeb.change_language(lang)
        if result and msg==lang:            
            self.update_ui_on_lang_change(lang)
        else:
            self.keeb_lang_menu.setTitle(f"Could not set {lang}: {msg}")

    def read_overlay_mapping_file(self, file):
        if not file:
            file = QFileDialog.getOpenFileName(None, 'Open file', '', "PolyKybd overlay mapping (*.poly.yaml)")
        if len(file) > 0:
            with open(file, 'r') as f:
                self.mapping = yaml.load(f, Loader=yaml.FullLoader)
        else:
            self.log.info("No file selected. Operation canceled.")

    def save_overlay_mapping_file(self, filename="overlay-mapping.poly.yaml"):
        with open(filename, "w") as f:
            f.write(yaml.dump(self.mapping))

    def quit_app(self):
        self.is_closing = True
        self.overlay_handler.close()
        self.quit()

    # noinspection PyPep8Naming
    def closeEvent(self, _):
        self.cmdMenu.disable_overlays()

    def send_overlay_data(self, data, allow_compressed):
        files = []
        if isinstance(data, str):
            files.append(get_overlay_path(data))
        else:
            for overlay in data:
                files.append(get_overlay_path(overlay))

        if len(files) > 0:
            try:
                self.cmdMenu.reset_overlays()
                self.keeb.send_overlays(files, allow_compressed)
            except Exception as e:
                self.log.warning(f"Failed to send overlays '{files}':{e}")
                self.log.warning("".join(traceback.format_exception(e)))

            self.keeb.set_idle(False)

    def active_window_reporter(self):
        self.last_update_msec = self.last_update_msec + UPDATE_CYCLE_MSEC
        self.last_update_10min_task = self.last_update_10min_task + UPDATE_CYCLE_MSEC
        lang = None
        if self.last_update_msec > RECONNECT_CYCLE_MSEC:
            lang = self.reconnect()
            self.last_update_msec = 0
        if self.connected:
            self.last_update_msec = RECONNECT_CYCLE_MSEC * 2 #just to limit that
            if lang and self.current_lang != lang:
                success, msg = self.helper.set_language(f"{lang[:2]}-{lang[2:]}")
                if success:
                    data = self.overlay_handler.get_overlay_data()
                    if data:
                        self.send_overlay_data(data, self.kb_sw_version[1] >= 5 and self.kb_sw_version[2] >= 4)
                else:
                    self.log.warning("Could not change OS language to '%s': %s", lang, msg)
                self.current_lang = lang

            data, cmd = self.overlay_handler.handle_active_window(UPDATE_CYCLE_MSEC, NEW_WINDOW_ACCEPT_TIME_MSEC)
            if cmd == OverlayCommand.DISABLE:
                self.keeb.disable_overlays()
            elif cmd == OverlayCommand.ENABLE:
                self.keeb.enable_overlays()

            if data and cmd == OverlayCommand.OFF_ON:
                self.send_overlay_data(data, self.kb_sw_version[1] >= 5 and self.kb_sw_version[2] >= 4)

            if self.last_update_10min_task > PERIODIC_10MIN_CYCLE_MSEC:
                self.last_update_10min_task = 0
                self.execute_10min_task()

        if not self.is_closing:
            QTimer.singleShot(UPDATE_CYCLE_MSEC, self.active_window_reporter)
        # except Exception as e:
        #    self.log.warning(f"Failed to report active window: {e}")

    def execute_10min_task(self):
        if self.settings.get("send_daylight_dependent_brightness"):
            brightness = self.sunlight.get_brightness_now()
            self.keeb.set_brightness(2+brightness*48)


