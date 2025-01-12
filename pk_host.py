import logging
import os
import platform
import re
import sys
import webbrowser

IS_PLASMA = os.getenv('XDG_CURRENT_DESKTOP')=="KDE"

if not IS_PLASMA:
    import pywinctl as pwc

import yaml
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox, QFileDialog


from CommandsSubMenu import CommandsSubMenu
from LinuxXInputHelper import LinuxXInputHelper
from LinuxPlasmaHelper import LinuxPlasmaHelper
from MacOSInputHelper import MacOSInputHelper
from PolyKybd import PolyKybd
from WindowsInputHelper import WindowsInputHelper


class PolyKybdHost(QApplication):
    def __init__(self):
        super().__init__(sys.argv)

        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(filename='log.txt'), logging.StreamHandler(stream=sys.stdout)]
        )
        self.log = logging.getLogger('PolyKybd')

        self.setQuitOnLastWindowClosed(False)
        self.win = None
        self.isClosing = False

        # Create the icon
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icons/pcolor.png"))

        # Create the tray
        tray = QSystemTrayIcon(parent=self)
        tray.setIcon(icon)
        tray.setVisible(True)

        # Create the menu
        self.menu = QMenu()
        self.menu.setStyleSheet("QMenu {icon-size: 64px;} QMenu::item {icon-size: 64px; background: transparent;}");

        self.keeb = PolyKybd()
        self.connected = False
        self.paused = False
        self.status = QAction(QIcon("icons/sync.svg"), "Waiting for PolyKybd...", parent=self)
        self.status.setToolTip("Press to pause connection")
        self.status.triggered.connect(self.pause)
        self.exit = QAction(QIcon("icons/power.svg"), "Quit", parent=self)
        self.exit.triggered.connect(self.quit_app)
        self.support = QAction(QIcon("icons/support.svg"), "Get Support", parent=self)
        self.support.triggered.connect(self.open_support)
        self.about = QAction(QIcon("icons/home.svg"), "About", parent=self)
        self.about.triggered.connect(self.open_about)
        self.reconnect()

        self.keeb_lang_menu = None
        self.menu.addAction(self.status)
        self.add_supported_lang(self.menu)

        lang_menu = self.menu.addMenu(QIcon("icons/language.svg"), "Change System Input Language")

        self.cmdMenu = CommandsSubMenu(self, self.keeb)
        self.cmdMenu.buildMenu(self.menu)

        action = QAction(QIcon("icons/overlays.svg"), "Send Shortcut Overlay...", parent=self)
        action.triggered.connect(self.send_shortcuts)
        self.menu.addAction(action)

        action = QAction(QIcon("icons/via.png"), "Configure Keymap (VIA)", parent=self)
        action.triggered.connect(self.open_via)
        self.menu.addAction(action)

        self.menu.addAction(self.support)
        self.menu.addAction(self.about)
        self.menu.addAction(self.exit)

        self.helper = None
        if platform.system() == "Windows":
            self.helper = WindowsInputHelper
        elif platform.system() == "Linux":
            if IS_PLASMA:
                self.helper = LinuxPlasmaHelper
            else:
                self.helper = LinuxXInputHelper
        elif platform.system() == "Darwin":
            self.helper = MacOSInputHelper

        # result = subprocess.run(['localectl', 'list-x11-keymap-layouts'], stdout=subprocess.PIPE)
        # entries = iter(result.stdout.splitlines())
        entries = self.helper.getLanguages(self.helper)

        for e in entries:
            self.log.info(f"Enumerating input language {e}")
            lang_menu.addAction(e, self.change_system_language)

        self.managed_connection_status()
        # Add the menu to the tray
        tray.setContextMenu(self.menu)
        tray.show()

        self.mapping = {}
        self.currentMappingEntry = None
        self.lastMappingEntry = None
        self.enable_mapping = True
        self.read_overlay_mapping_file("overlay-mapping.poly.yaml")
        # self.mapping["Inkscape"] = dict(app="inkscape", title=".*Inkscape",
        #                                 overlay="overlays/inkscape_template.mods.png")
        # self.mapping["Gimp"] = dict(app="gimp-2.*",
        #                             overlay="overlays/gimp_template.png")
        # self.mapping["KiCad PcbNew"] = dict(app="kicad", title="PCB Editor",
        #                                     overlay="overlays/kicad_pcb_template.png")
        # self.save_overlay_mapping_file()

        QTimer.singleShot(1000, self.activeWindowReporter)

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
            self.status.setText(f"Reconnect")
            self.connected = False
            self.status.setToolTip("")
        else:
            self.status.setToolTip("Press to pause connection")
        self.managed_connection_status()

    def reconnect(self):
        if not self.paused:
            result = self.keeb.connect()

            if result != self.connected:
                self.connected, msg = self.keeb.query_version_info()
                if self.connected:
                    if self.keeb.get_sw_version() == "0.5.2":
                        self.status.setIcon(QIcon("icons/sync.svg"))
                        self.status.setText(
                            f"PolyKybd {self.keeb.get_name()} {self.keeb.get_hw_version()} ({self.keeb.get_sw_version()})")

                    else:
                        self.status.setIcon(QIcon("icons/sync_disabled.svg"))
                        self.status.setText(f"Incompatible version: {msg}")
                        self.connected = False
                else:
                    self.status.setIcon(QIcon("icons/sync_disabled.svg"))
                    self.status.setText(msg)
            self.managed_connection_status()

    def add_supported_lang(self, menu):
        result, msg = self.keeb.enumerate_lang()
        if result:
            self.keeb_lang_menu = menu.addMenu(f"Selected Language: {self.keeb.get_current_lang()}")
            all_languages = list(filter(None, msg.split(",")))
            for lang in all_languages:
                item = self.keeb_lang_menu.addAction(lang, self.change_keeb_language)
                item.setData(lang)

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
            self.keeb.send_overlay(fname[0])
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
        if result:
            self.keeb_lang_menu.setTitle(f"Selected Language: {msg}")
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
        with open(filename, 'w') as f:
            f.write(yaml.dump(self.mapping))

    def quit_app(self):
        self.isClosing = True
        self.quit()

    def closeEvent(self, event):
        self.cmdMenu.disable_overlays()

    def tryToMatchWindow(self, name, entry, app_name, title):
        match = ("overlay" in entry.keys()) and (
                "app" in entry.keys() or "title" in entry.keys())
        try:
            if app_name and match and "app" in entry:
                match = match and re.search(entry["app"], app_name)
            if title and match and "title" in entry:
                match = match and re.search(entry["title"], title)
        except re.error as e:
            self.log.warning(f"Cannot match entry '{name}': {entry}, because '{e.msg}'@{e.pos} with '{e.pattern}'")
            return False

        if match:
            if self.lastMappingEntry == entry:
                self.cmdMenu.enable_overlays()
                self.currentMappingEntry = entry
            else:
                self.cmdMenu.disable_overlays()
                self.cmdMenu.reset_overlays()
                overlays = entry["overlay"]
                if isinstance(overlays, str):
                    try:
                        self.keeb.send_overlay(overlays)
                    except:
                        self.log.warning(f"Failed to send overlay '{overlays}'")
                else:
                    self.keeb.disable_overlays()
                    for o in overlays:
                        try:
                            self.keeb.send_overlay(o, False)
                        except:
                            self.log.warning(f"Failed to send overlay '{o}'")
                    self.keeb.enable_overlays()
                # self.log.info(f"Found overlay {entry['overlay']} for {name}")
                self.currentMappingEntry = entry
                self.lastMappingEntry = entry
            self.keeb.set_idle(False)
            return True
        return False

    def activeWindowReporter(self):
        self.reconnect()
        if self.connected:
            win = pwc.getActiveWindow()
            if win:
                if self.win is None or win.getHandle() != self.win.getHandle():
                    self.win = win
                    if self.enable_mapping:
                        try:
                            name = self.win.getAppName()
                            title = self.win.title
                            
                            if platform.system() == 'Windows':
                                self.log.info(
                                    f"Active App Changed: \"{name}\", Title: \"{title}\"  Handle: {self.win.getHandle()}")
                            else:
                                self.log.info(
                                    f"Active App Changed: \"{name}\", Title: \"{title}\"  Handle: {self.win.getHandle()} Parent: {self.win.getParent()}")
                            if self.enable_mapping and self.mapping:
                                found = False
                                for n, entry in self.mapping.items():
                                    found = self.tryToMatchWindow(n, entry, name, title)
                                    if found:
                                        break
                                if self.currentMappingEntry and not found:
                                    self.cmdMenu.disable_overlays()
                                    self.currentMappingEntry = None
                        except Exception as e:
                            self.log.warning(f"Failed retrieving active window: {e}")
            else:
                if self.win:
                    self.log.info("No active window")
                    self.win = None
                    if self.enable_mapping and self.currentMappingEntry:
                        self.cmdMenu.disable_overlays()
                        self.currentMappingEntry = None
        else:
            self.win = None
        if not self.isClosing:
            QTimer.singleShot(500, self.activeWindowReporter)

    # except Exception as e:
    #    self.log.warning(f"Failed to report active window: {e}")


if __name__ == '__main__':
    app = PolyKybdHost()
    print("Executing PolyKybd Host...")
    sys.exit(app.exec_())
