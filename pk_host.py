import os
import platform
import logging
import sys
import webbrowser

import pywinctl as pwc
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox, QFileDialog

from LinuxXInputHelper import LinuxXInputHelper
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

        # Create the icon
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icons/pcolor.png"))

        # Create the tray
        tray = QSystemTrayIcon(parent=self)
        tray.setIcon(icon)
        tray.setVisible(True)

        # Create the menu
        menu = QMenu()
        self.keeb = PolyKybd()
        self.keeb.connect()
        result, msg = self.keeb.queryId()

        if result == True:
            self.status = QAction(QIcon("icons/sync.png"), f"Connected to: {msg}", parent=self)
            self.status.setData(True)
            self.status.triggered.connect(self.reconnect)
            menu.addAction(self.status)
            self.add_supported_lang(menu)
        else:
            self.status = QAction(QIcon("icons/sync_disabled.png"), msg, parent=self)
            self.status.setData(False)
            self.status.triggered.connect(self.reconnect)
            menu.addAction(self.status)

        action = QAction(QIcon("icons/via.png"), "Configure Keymap (VIA)", parent=self)
        action.triggered.connect(self.open_via)
        menu.addAction(action)

        langMenu = menu.addMenu(QIcon("icons/lang.png"), "Change System Input Language")

        action = QAction(QIcon("icons/overlays.png"), "Send Shortcut Overlay...", parent=self)
        action.triggered.connect(self.send_shortcuts)
        menu.addAction(action)

        action = QAction(QIcon("icons/delete.png"), "Reset Overlays Buffers", parent=self)
        action.triggered.connect(self.reset_overlays)
        menu.addAction(action)

        action = QAction(QIcon("icons/toggle_on.png"), "Enable Shortcut Overlays", parent=self)
        action.triggered.connect(self.enable_overlays)
        menu.addAction(action)

        action = QAction(QIcon("icons/toggle_off.png"), "Disable Shortcut Overlays", parent=self)
        action.triggered.connect(self.disable_overlays)
        menu.addAction(action)

        action = QAction(QIcon("icons/support.png"), "Get Support", parent=self)
        action.triggered.connect(self.open_support)
        menu.addAction(action)

        action = QAction(QIcon("icons/home.png"), "About", parent=self)
        action.triggered.connect(self.open_about)
        menu.addAction(action)

        quit = QAction(QIcon("icons/power.png"), "Quit", parent=self)
        quit.triggered.connect(self.quit)
        menu.addAction(quit)

        self.helper = None
        if platform.system() == "Windows":
            self.helper = WindowsInputHelper
        elif platform.system() == "Linux":
            self.helper = LinuxXInputHelper

        # result = subprocess.run(['localectl', 'list-x11-keymap-layouts'], stdout=subprocess.PIPE)
        # entries = iter(result.stdout.splitlines())
        entries = self.helper.getLanguages(self)

        for e in entries:
            print(f"Enumerating input language {e}")
            langMenu.addAction(e, self.change_system_language)

        # Add the menu to the tray
        tray.setContextMenu(menu)
        tray.show()

    def reconnect(self):
        result = self.keeb.connect()

        if result != self.status.data():
            result, msg = self.keeb.queryId()
            if result == True:
                self.status.setIcon(QIcon("icons/sync.png"))
                self.status.setText(f"Connected to: {msg}")
                self.status.setData(True)
            else:
                self.status.setIcon(QIcon("icons/sync_disabled.png"))
                self.status.setText(msg)
                self.status.setData(False)

    def add_supported_lang(self, menu):
        result, msg = self.keeb.enumerate_lang()
        if result == True:
            self.keeb_lang_menu = menu.addMenu(f"Selected Language: {self.keeb.get_current_lang()}")
            all_languages = list(filter(None, msg.split(",")))
            for lang in all_languages:
                item = self.keeb_lang_menu.addAction(lang, self.change_keeb_language)
                item.setData(lang)

    def open_via(self):
        webbrowser.open("https://usevia.app", new=0, autoraise=True)

    def open_support(self):
        webbrowser.open("https://discord.gg/5eU48M79", new=0, autoraise=True)

    def open_about(self):
        webbrowser.open("https://ko-fi.com/polykb", new=0, autoraise=True)

    def send_shortcuts(self):
        fname = QFileDialog.getOpenFileName(None, 'Open file', '', "Image files (*.jpg *.gif *.png *.bmp *jpeg)")
        if len(fname) > 0:
            self.keeb.send_overlay(fname[0])
        else:
            msg = QMessageBox()
            msg.setWindowTitle("Info")
            msg.setText("No file selected. Operation canceled.")
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()

    def change_system_language(self):
        lang = self.sender().text()
        output = self.helper.setLanguage(self, lang)
        if output:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText(f"Changing input language to '{lang}' failed with:\n\"{output}\"")
            msg.setIcon(QMessageBox.Critical)
            msg.exec_()
        else:
            msg = QMessageBox()
            msg.setWindowTitle("Success")
            msg.setText(f"Change input language to '{lang}'.")
            msg.setIcon(QMessageBox.Information)
            msg.exec_()

    def reset_overlays(self):
        result, msg = self.keeb.reset_overlays()
        if result == False:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText(f"Failed clearing overlays: {msg}")
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()

    def enable_overlays(self):
        result, msg = self.keeb.enable_overlays()
        if result == False:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText(f"Failed enabling overlays: {msg}")
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()

    def disable_overlays(self):
        result, msg = self.keeb.disable_overlays()
        if result == False:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText(f"Failed disabling overlays: {msg}")
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()

    def change_keeb_language(self):
        lang = self.sender().data()
        result, msg = self.keeb.change_language(lang)
        if result == True:
            self.keeb_lang_menu.setTitle(f"Selected Language: {msg}")
        else:
            self.keeb_lang_menu.setTitle(f"Could not set {lang}: {msg}")

    def activeWindowReporter(self):
        win = pwc.getActiveWindow()
        if win:
            if self.win is None or win.getHandle() != self.win.getHandle():
                self.win = win
                self.log.info(
                    f"Active App Changed: \"{self.win.getAppName()}\", Title: \"{self.win.title}\"  Handle: {self.win.getHandle()} Parent: {self.win.getParent()}")
        else:
            if self.win:
                self.log.info("No active window")
                self.win = None


if __name__ == '__main__':
    app = PolyKybdHost()
    print("Executing PolyKybd Host...")
    timer = QTimer(app)
    timer.timeout.connect(app.activeWindowReporter)
    timer.timeout.connect(app.reconnect)
    timer.start(1000)

    sys.exit(app.exec_())
