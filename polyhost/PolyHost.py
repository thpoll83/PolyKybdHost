import logging
import os
import platform
import sys
import traceback
import webbrowser
import yaml

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon, QCursor, QPalette, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QAction,
    QMessageBox,
    QFileDialog,
)

from device import PolyKybd, PolyKybdMock
from input import (
    LinuxGnomeInputHelper,
    LinuxPlasmaHelper,
    MacOSInputHelper,
    WindowsInputHelper,
)
from _version import __version__

import CommandsSubMenu
import handler.OverlayHandler as OverlayHandler

IS_PLASMA = os.getenv("XDG_CURRENT_DESKTOP") == "KDE"

UPDATE_CYCLE_MSEC = 250
RECONNECT_CYCLE_MSEC = 1000
NEW_WINDOW_ACCEPT_TIME_MSEC = 1000

def sort_by_country_abc(item):
    return item[2:]


def get_overlay_path(filepath):
    return os.path.join(os.path.dirname(__file__), "overlays", filepath)


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

        self.setQuitOnLastWindowClosed(False)
        self.is_closing = False

        # Create the icon
        icon = QIcon("polyhost/icons/pcolor.png")

        # Create the tray
        self.tray = QSystemTrayIcon(parent=self)
        self.tray.setIcon(icon)
        self.tray.setVisible(True)
        self.tray.setToolTip(f"PolyKybdHost {__version__}")

        # Create the menu
        self.menu = QMenu()
        self.menu.setStyleSheet("QMenu {icon-size: 64px;} QMenu::item {icon-size: 64px; background: transparent;}");

        # self.keeb = PolyKybdMock.PolyKybdMock(f"{__version__}")
        self.keeb = PolyKybd.PolyKybd()
        self.connected = False
        self.paused = False
        self.status = QAction(QIcon("polyhost/icons/sync.svg"), "Waiting for PolyKybd...", parent=self)
        self.status.setToolTip("Press to pause connection")
        self.status.triggered.connect(self.pause)
        self.exit = QAction(QIcon("polyhost/icons/power.svg"), "Quit", parent=self)
        self.exit.triggered.connect(self.quit_app)
        self.support = QAction(QIcon("polyhost/icons/support.svg"), "Get Support", parent=self)
        self.support.triggered.connect(self.open_support)
        self.about = QAction(QIcon("polyhost/icons/home.svg"), "About", parent=self)
        self.about.triggered.connect(self.open_about)
        self.reconnect()

        self.last_update_msec = 0
        self.current_lang = None
        self.keeb_lang_menu = None
        self.menu.addAction(self.status)
        self.add_supported_lang(self.menu)

        lang_menu = self.menu.addMenu(QIcon("polyhost/icons/language.svg"), "Change System Input Language")

        self.cmdMenu = CommandsSubMenu.CommandsSubMenu(self, self.keeb)
        self.cmdMenu.buildMenu(self.menu)

        action = QAction(QIcon("polyhost/icons/overlays.svg"), "Send Shortcut Overlay...", parent=self)
        action.triggered.connect(self.send_shortcuts)
        self.menu.addAction(action)

        action = QAction(QIcon("polyhost/icons/via.png"), "Configure Keymap (VIA)", parent=self)
        action.triggered.connect(self.open_via)
        self.menu.addAction(action)

        self.menu.addAction(self.support)
        self.menu.addAction(self.about)
        self.menu.addAction(self.exit)

        self.helper = None
        if platform.system() == "Windows":
            self.helper = WindowsInputHelper.WindowsInputHelper
        elif platform.system() == "Linux":
            if IS_PLASMA:
                self.helper = LinuxPlasmaHelper.LinuxPlasmaHelper
            else:
                self.helper = LinuxGnomeInputHelper.LinuxGnomeInputHelper
        elif platform.system() == "Darwin":
            self.helper = MacOSInputHelper.MacOSInputHelper

        entries = self.helper.getLanguages(self.helper)

        result = self.helper.getCurrentLanguage(self.helper)
        if result:
            success, sys_lang = result
            if success:
                self.log.info(f"Current System Language: {sys_lang}")
            else:
                self.log.warning("Could not query current System Language.")
        else:
            self.log.warning("Could not connect to PolyKybd.")

        for e in entries:
            self.log.info(f"Enumerating input language {e}")
            lang_menu.addAction(e, self.change_system_language)

        self.managed_connection_status()
        # Add the menu to the tray
        #self.tray.activated.connect(self.on_activated)
        self.tray.setContextMenu(self.menu)
        self.tray.show()

        self.mapping = {}
        self.read_overlay_mapping_file("polyhost/overlays/overlay-mapping.poly.yaml")

        self.overlay_handler = OverlayHandler.OverlayHandler(self.mapping)

        self.setStyle("Fusion")
        # Now use a palette to switch to dark colors:
        palette = QPalette()
        baseColor = QColor(35, 35, 35)
        windowBaseColor = QColor(99, 99, 99)
        textColor = QColor(150, 150, 150)
        highlightTextColor = QColor(255, 255, 255)
        palette.setColor(QPalette.Window, windowBaseColor)
        palette.setColor(QPalette.WindowText, textColor)
        palette.setColor(QPalette.Base, baseColor)
        palette.setColor(QPalette.AlternateBase, windowBaseColor)
        palette.setColor(QPalette.ToolTipBase, baseColor)
        palette.setColor(QPalette.ToolTipText, textColor)
        palette.setColor(QPalette.Text,textColor)
        palette.setColor(QPalette.Button, windowBaseColor)
        palette.setColor(QPalette.ButtonText, textColor)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, highlightTextColor)
        self.setPalette(palette)

        QTimer.singleShot(1000, self.activeWindowReporter)

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
            if not hasattr(self, 'hid'):
                if self.keeb.connect():
                    result, lang = self.keeb.query_current_lang()
            else:
                result, lang = self.keeb.query_current_lang()

            if result != self.connected:
                self.connected, msg = self.keeb.query_version_info()
                if self.connected:
                    kb_version = self.keeb.get_sw_version()
                    expected = __version__
                    if kb_version.startswith(expected[:3]):
                        if kb_version != expected:
                            self.log.warning(f"Warning! Minor version mismatch, expected {expected}, got {kb_version}'.")
                            self.status.setIcon(QIcon("polyhost/icons/sync_problem.svg"))
                            self.status.setText(
                                f"PolyKybd {self.keeb.get_name()} {self.keeb.get_hw_version()} ({kb_version}, please update to {expected}!)")
                        else:
                            self.status.setIcon(QIcon("polyhost/icons/sync.svg"))
                            self.status.setText(
                                f"PolyKybd {self.keeb.get_name()} {self.keeb.get_hw_version()} ({kb_version})")
                        if result:
                            self.update_ui_on_lang_change(lang)
                    else:
                        self.status.setIcon(QIcon("polyhost/icons/sync_disabled.svg"))
                        self.status.setText(f"Incompatible version: {msg}, expected {expected}, got {kb_version}'.")
                        self.connected = False
                else:
                    self.status.setIcon(QIcon("polyhost/icons/sync_disabled.svg"))
                    self.status.setText(msg)
            self.managed_connection_status()
            return lang
        return self.current_lang

    def langcode_to_flag(self, lang_code):
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
        if hasattr(self, 'keeb_lang_menu'):
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

    @staticmethod
    def open_support():
        webbrowser.open("https://discord.gg/5eU48M79", new=0, autoraise=True)

    @staticmethod
    def open_about():
        webbrowser.open("https://ko-fi.com/polykb", new=0, autoraise=True)

    def send_shortcuts(self):
        fname = QFileDialog.getOpenFileName(None, 'Open file', '', "Image files (*.jpg *.gif *.png *.bmp *.jpeg)")
        if len(fname) > 0:
            self.keeb.send_overlays(fname[0])
        else:
            self.log.info("No file selected. Operation canceled.")

    def change_system_language(self):
        lang = self.sender().text()
        output = self.helper.setLanguage(self, lang)
        if output:
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

    def closeEvent(self, _):
        self.cmdMenu.disable_overlays()

    def sendOverlayData(self, data):
        files = []
        if isinstance(data, str):
            files.append(get_overlay_path(data))
        else:
            for overlay in data:
                files.append(get_overlay_path(overlay))

        if len(files) > 0:
            try:
                self.cmdMenu.reset_overlays()
                self.keeb.send_overlays(files)
            except Exception as e:
                self.log.warning(f"Failed to send overlays '{files}':{e}")
                self.log.warning("".join(traceback.format_exception(e)))

            self.keeb.set_idle(False)

    def activeWindowReporter(self):
        self.last_update_msec = self.last_update_msec + UPDATE_CYCLE_MSEC
        lang = None
        if self.last_update_msec > RECONNECT_CYCLE_MSEC:
            lang = self.reconnect()
            self.last_update_msec = 0
        if self.connected:
            self.last_update_msec = RECONNECT_CYCLE_MSEC * 2 #just to limit that
            if lang and self.current_lang != lang:
                if self.helper.setLanguage(self.helper, f"{lang[:2]}-{lang[2:]}"):
                    data = self.overlay_handler.getOverlayData()
                    if data:
                        self.sendOverlayData(data)
                else:
                    self.log.warning("Could not change OS language to '%s'", lang)
                self.current_lang = lang

            data, cmd = self.overlay_handler.handleActiveWindow(UPDATE_CYCLE_MSEC, NEW_WINDOW_ACCEPT_TIME_MSEC)
            if cmd == OverlayHandler.OverlayCommand.DISABLE:
                self.keeb.disable_overlays()
            elif cmd == OverlayHandler.OverlayCommand.ENABLE:
                self.keeb.enable_overlays()

            if data and cmd == OverlayHandler.OverlayCommand.OFF_ON:
                self.sendOverlayData(data)

        if not self.is_closing:
            QTimer.singleShot(UPDATE_CYCLE_MSEC, self.activeWindowReporter)

    # except Exception as e:
    #    self.log.warning(f"Failed to report active window: {e}")
