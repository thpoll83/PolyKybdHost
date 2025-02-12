import logging
import os
import ipaddress
import platform
import re
import socket
import sys
import time
import threading
import webbrowser
import yaml

from _version import __version__
from PolyKybd import PolyKybd
from CommandsSubMenu import CommandsSubMenu
from LinuxXInputHelper import LinuxXInputHelper
from LinuxPlasmaHelper import LinuxPlasmaHelper
from MacOSInputHelper import MacOSInputHelper
from WindowsInputHelper import WindowsInputHelper

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon, QCursor, QPalette, QColor
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox, QFileDialog

IS_PLASMA = os.getenv('XDG_CURRENT_DESKTOP')=="KDE"

if not IS_PLASMA:
    import pywinctl as pwc


TCP_PORT = 50162
BUFFER_SIZE = 1024

def sort_by_country_abc(item):
    return item[2:]

# Needs to be started as thread
def receiveFromForwarder(log, connections):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        sock.bind(("", TCP_PORT))
    except socket.error as message:
        log.warning(f"Failed to bind socket: {message}")
        sock.close()
        return
    
    sock.listen(5)
    sock.settimeout(10.0)
    
    while len(connections)>0:
        try:
            conn, (addr, _) = sock.accept()
            data = conn.recv(BUFFER_SIZE)
            data = data.decode("utf-8")
            entries = [0,"",""] if not data else data.split(";")
            if len(entries)>2:
                lookup = {}
                lookup["handle"] = entries[0]
                lookup["name"] = entries[1]
                lookup["title"] = entries[2]
                connections[addr] = lookup
        except socket.timeout:
            time.sleep(3)
    conn.close()
    sock.close()
    
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

        self.setQuitOnLastWindowClosed(False)
        self.win = None
        self.isClosing = False

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

        self.keeb = PolyKybd()
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

        self.keeb_lang_menu = None
        self.menu.addAction(self.status)
        self.add_supported_lang(self.menu)

        lang_menu = self.menu.addMenu(QIcon("polyhost/icons/language.svg"), "Change System Input Language")

        self.cmdMenu = CommandsSubMenu(self, self.keeb)
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

        success, sys_lang = self.helper.getCurrentLanguage(self.helper)
        if success:
            self.log.info(f"Current System Language: {sys_lang}")
        else:
            self.log.warning("Could not query current System Language.")

        for e in entries:
            self.log.info(f"Enumerating input language {e}")
            lang_menu.addAction(e, self.change_system_language)

        self.managed_connection_status()
        # Add the menu to the tray
        self.tray.activated.connect(self.on_activated)
        self.tray.setContextMenu(self.menu)
        self.tray.show()

        self.mapping = {}
        self.forwarder_entry = None
        self.currentMappingEntry = None
        self.currentRemoteMappingEntry = None
        self.lastMappingEntry = None
        self.enable_mapping = True
        self.read_overlay_mapping_file("polyhost/overlays/overlay-mapping.poly.yaml")
        
        self.connections = {}
        self.forwarder = None
        self.listen_to_forwarder()
            
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

    def listen_to_forwarder(self):
        resolved_remote = False
        for _, entry in self.mapping.items():
            if "remote" in entry.keys():
                remote = entry["remote"]
                try:
                    addr = str(ipaddress.ip_address(remote))
                    if not addr in self.connections.keys():
                        self.connections[addr] = ""
                        self.log.info(f"IP address {remote} used with {addr}")
                        resolved_remote = True
                        entry["ip"] = addr
                        
                except ValueError:
                    try:
                        addr = str(socket.gethostbyname(remote))
                        if not addr in self.connections.keys():
                            self.connections[addr] = ""
                            self.log.info(f"Resolved {remote} to {addr}")
                            resolved_remote = True
                            entry["ip"] = addr
                    except:
                        self.log.warning(f"Could not resolve {remote}")
                except:
                    self.log.warning(f"Could not resolve {remote}")    
        if resolved_remote:
            if not self.forwarder:
                self.forwarder = threading.Thread(target = receiveFromForwarder, name = f"PolyKybd Forwarder", args = (self.log, self.connections))
                self.forwarder.start()
        else:
            self.forwarder = None
                    
    def on_activated(self, i_reason):
        if i_reason == QSystemTrayIcon.Trigger:
            if not self.menu.isVisible():
                self.menu.popup(QCursor.pos())
            else:
                self.menu.hide()
                    
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
                    kbVersion = self.keeb.get_sw_version()
                    expected = __version__
                    if kbVersion.startswith(expected[:3]):
                        if kbVersion != expected:
                            self.log.warning(f"Warning! Minor version mismatch, expected {expected}, got {kbVersion}'.")
                            self.status.setIcon(QIcon("polyhost/icons/sync_problem.svg"))
                            self.status.setText(
                                f"PolyKybd {self.keeb.get_name()} {self.keeb.get_hw_version()} ({kbVersion}, please update to {expected}!)")
                        else:
                            self.status.setIcon(QIcon("polyhost/icons/sync.svg"))
                            self.status.setText(
                                f"PolyKybd {self.keeb.get_name()} {self.keeb.get_hw_version()} ({kbVersion})")
                        success, current_lang = self.keeb.query_current_lang()
                        if success:
                            self.update_ui_on_lang_change(current_lang)
                    else:
                        self.status.setIcon(QIcon("polyhost/icons/sync_disabled.svg"))
                        self.status.setText(f"Incompatible version: {msg}, expected {expected}, got {kbVersion}'.")
                        self.connected = False
                else:
                    self.status.setIcon(QIcon("polyhost/icons/sync_disabled.svg"))
                    self.status.setText(msg)
            self.managed_connection_status()


    def langcode_to_flag(self, lang_code):
        result = ""
        for ch in lang_code:
            num = 0x1F1E6 + ord(ch.upper()) - ord('A')
            result = f"{result}{chr(num)}"
        return result
        
    def add_supported_lang(self, menu):
        result, msg = self.keeb.enumerate_lang()
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
        with open(filename, 'w') as f:
            f.write(yaml.dump(self.mapping))

    def quit_app(self):
        self.isClosing = True
        
        self.connections = {}
        if self.forwarder:
            self.forwarder.join()
                
        self.quit()

    def closeEvent(self, event):
        self.cmdMenu.disable_overlays()

    def sendOverlayData(self, data, onOff = True):
        if isinstance(data, str):
            try:
                self.keeb.send_overlay(get_overlay_path(data), onOff)
            except:
                self.log.warning(f"Failed to send overlay '{data}'")
        else:
            if onOff:
                self.keeb.disable_overlays()
            for overlay in data:
                try:
                    self.keeb.send_overlay(get_overlay_path(overlay), False)
                except:
                    self.log.warning(f"Failed to send overlay '{overlay}'")
            if onOff:
                self.keeb.enable_overlays()
            
    def tryToMatchWindow(self, name, entry, appName, title, from_forwarder):
        overlay = "overlay" in entry.keys()
        remote = "remote" in entry.keys()
        ip = "ip" in entry.keys()
        
        match = (overlay or remote) and ("app" in entry.keys() or "title" in entry.keys())
        try:
            if appName and match and "app" in entry:
                match = match and re.search(entry["app"], appName)
                if match:
                    if "titles" in entry.keys():
                        for subentryName, subentry in entry["titles"].items():
                            if self.tryToMatchWindow(subentryName, subentry, appName, title, from_forwarder):
                                return True
            if title and match and "title" in entry:
                match = match and re.search(entry["title"], title)
        except re.error as e:
            self.log.warning(f"Cannot match entry '{name}': {entry}, because '{e.msg}'@{e.pos} with '{e.pattern}'")
            return False

        if match:
            if overlay:
                if self.lastMappingEntry == entry:
                    self.cmdMenu.enable_overlays()
                    self.currentMappingEntry = entry
                else:
                    self.cmdMenu.disable_overlays()
                    self.cmdMenu.reset_overlays()
                    self.sendOverlayData(entry["overlay"])
                    # self.log.info(f"Found overlay {entry['overlay']} for {name}")
                    self.currentMappingEntry = entry
                    self.lastMappingEntry = entry
                self.keeb.set_idle(False)
                return True
            else: #ip/remote
                if not ip:
                    self.listen_to_forwarder()
                else:
                    self.currentMappingEntry = entry
                    self.lastMappingEntry = entry
                    #now check the remote data
                    if from_forwarder:
                        return self.remoteWindowReporter(from_forwarder)
                    return True
        return False         
        
        
    def remoteWindowReporter(self, forwarder_data):
        self.log.info(f"Test Remote App: Title: {self.remote_title} with {forwarder_data}")
        if forwarder_data and len(forwarder_data)>2 and self.remote_handle != forwarder_data["handle"] and self.remote_title != forwarder_data["title"]:
            self.remote_handle = forwarder_data["handle"]
            self.remote_title = forwarder_data["title"]
            appName = forwarder_data["name"]
            self.log.info(
                        f"Remote App Changed: \"{appName}\", Title: \"{self.remote_title}\"  Handle: {self.remote_handle}")
            if self.enable_mapping:
                found = False
                for entryName, entry in self.mapping.items():
                    found = self.tryToMatchWindow(entryName, entry, appName, self.remote_title, None)
                    if found:
                        self.currentRemoteMappingEntry = entry
                        break
                if self.currentRemoteMappingEntry and not found:
                    self.cmdMenu.disable_overlays()
                    self.currentRemoteMappingEntry = None
            return True
        return False
        
    def activeWindowReporter(self):
        self.reconnect()
        if self.connected:
            received, lang = self.keeb.query_current_lang()
            if received and self.current_lang != lang:
                self.helper.setLanguage(self.helper, f"{lang[:2]}-{lang[2:]}")
            win = pwc.getActiveWindow()
            #self.log.info(f"App : \"{win.getAppName()}\", Title: \"{win.title}\"  Handle: {win.getHandle()}")
            if win:
                from_forwarder = None
                remote_changed = False
                current = self.currentMappingEntry
                
                if current and "ip" in current.keys() and self.connections[current["ip"]]:
                    self.forwarder_entry = current
                    from_forwarder = self.connections[current["ip"]]
                local_win_changed = (self.win is None or win.getHandle() != self.win.getHandle() or win.title != self.title)
                
                #self.log.info(f"Current: \"{current}\" FromForwarder:\"{from_forwarder}\"")
                
                if local_win_changed:
                    self.remote_handle = None
                    self.remote_title = None
                    self.win = win
                    self.title = win.title
                    if self.enable_mapping:
                        try:
                            appName = self.win.getAppName()
                            title = self.win.title
                            
                            if platform.system() == 'Windows':
                                self.log.info(
                                    f"Active App Changed: \"{appName}\", Title: \"{title.encode('utf-8')}\"  Handle: {self.win.getHandle()}")
                            else:
                                self.log.info(
                                    f"Active App Changed: \"{appName}\", Title: \"{title.encode('utf-8')}\"  Handle: {self.win.getHandle()} Parent: {self.win.getParent()}")
                            if self.enable_mapping and self.mapping:
                                found = False
                                for entryName, entry in self.mapping.items():
                                    found = self.tryToMatchWindow(entryName, entry, appName, title, from_forwarder)
                                    if found:
                                        break
                                if self.currentMappingEntry and not found:
                                    self.cmdMenu.disable_overlays()
                                    self.currentMappingEntry = None
                        except Exception as e:
                            self.log.warning(f"Failed retrieving active window: {e}")
                elif self.forwarder_entry and self.forwarder_entry == current:
                    remote_changed = self.remoteWindowReporter(self.connections[self.forwarder_entry["ip"]])
                    if remote_changed:
                        self.win = None
                        self.title = None
                
                if not remote_changed and not local_win_changed and self.enable_mapping and self.currentMappingEntry and received and lang!=self.current_lang:
                    # the language changed so maybe the overlay icons shifted from right to left (== need to resend)
                    if self.currentMappingEntry and "overlay" in self.currentMappingEntry:
                        self.sendOverlayData(self.currentMappingEntry["overlay"], False)
                    elif self.currentRemoteMappingEntry and "overlay" in self.currentRemoteMappingEntry:
                        self.sendOverlayData(self.currentRemoteMappingEntry["overlay"], False)
            else:
                if self.win:
                    self.log.info("No active window")
                    self.win = None
                    self.title = None
                    if self.enable_mapping and self.currentMappingEntry:
                        self.cmdMenu.disable_overlays()
                        self.currentMappingEntry = None
            if received:
                self.current_lang = lang
        else:
            self.win = None
            self.title = None
        if not self.isClosing:
            QTimer.singleShot(500, self.activeWindowReporter)

    # except Exception as e:
    #    self.log.warning(f"Failed to report active window: {e}")
