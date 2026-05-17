import logging
from logging.handlers import RotatingFileHandler
import os
import pathlib
import platform
import sys
import time
import webbrowser
import yaml

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QAction,
    QDialog,
    QMessageBox,
    QFileDialog, )

from polyhost.gui.get_icon import get_icon
from polyhost.gui.icon_state_manager import IconStateManager
from polyhost.gui.log_viewer import LogViewerDialog
from polyhost.gui.layout_dialog.kb_layout_dialog import KbLayoutDialog
from polyhost.gui.settings_dialog import SettingsDialog
from polyhost.gui.cmd_menu import CommandsSubMenu
from polyhost.handler.active_window import OverlayHandler
from polyhost.handler.common import OverlayCommand
from polyhost.input.linux_gnome_helper import LinuxGnomeInputHelper
from polyhost.input.linux_kde_helper import LinuxPlasmaHelper
from polyhost.input.macos_helper import MacOSInputHelper
from polyhost.input.win_helper import WindowsInputHelper
from polyhost.services.unicode_cache import UnicodeCache
from polyhost.settings import PolySettings
from polyhost.device.poly_kybd import PolyKybd
from polyhost.device.poly_kybd_mock import PolyKybdMock
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.device_manager import DeviceManager
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

def get_lang_and_country(combined : str):
    return combined[:2], combined[2:]


from polyhost.util.log_util import DEBUG_DETAILED, ColorFormatter, make_stream_handler


class MultiLineFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        lines = message.splitlines()
        if len(lines)==1:
            return message.strip("\n")
        timestamp = self.formatTime(record)
        formatted_lines = [f"[{timestamp}] {line}" for line in lines[:-1]]
        return lines[0] + "\n".join(formatted_lines)


class PolyHost(QApplication):
    def __init__(self, log_level, debug_mode):
        super().__init__(sys.argv)
        fmt = "[%(asctime)s] %(levelname)-7s {%(filename)s:%(lineno)d} %(message)s" if debug_mode>0 else "[%(asctime)s] %(levelname)-7s %(message)s"
        level = DEBUG_DETAILED if debug_mode>1 else log_level

        file_handler = RotatingFileHandler(
            filename="host_log.txt",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(fmt))

        stream_handler = make_stream_handler(fmt)

        logging.basicConfig(level=level, handlers=[file_handler, stream_handler])
        self.log = logging.getLogger('PolyHost')

        # Create the tray
        self.tray = QSystemTrayIcon(parent=self)
        self.icon_manager = IconStateManager(self, False, f"PolyKybdHost {__version__}")
        self.tray.setVisible(True)

        self.keeb_log = logging.getLogger("PolyKybdConsole")
        self.keeb_log.setLevel(logging.INFO)  # Set log level for logger 'b'

        # Add a file handler for 'b' (with a different filename)
        file_handler = RotatingFileHandler(
            filename="polykybd_console.txt",  # Separate log file for 'b'
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setFormatter(MultiLineFormatter(fmt="[%(asctime)s] %(message)s"))
        self.keeb_log.addHandler(file_handler)
        self.keeb_log.propagate = False

        self.kb_sw_version = None
        self.connected = False
        self.paused = False
        self.poly_settings = PolySettings()
        self.device_settings = DeviceSettings()
        self.keeb = PolyKybd(self.device_settings, self.poly_settings)

        self.device_mgr = DeviceManager(self.device_settings)
        self.device_mgr.add(self.keeb, "PolyKybd", is_primary=True)
        if self.poly_settings.get("dev_mock_enabled"):
            mock = PolyKybdMock(self.device_settings, f"{__version__}")
            self.device_mgr.add(mock, "PolyKybdMock", is_primary=False)
            self.log.info("Mock device added as secondary.")

        connected = self.keeb.connect()
        self.device_mgr.connect_secondaries()
        self.device_mgr.reset_all_caches()
        if connected:
            self.log.info("Connected to PolyKybd.")
        else:
            self.log.info("Not yet connected to PolyKybd...")
        
        
        self.setApplicationName('PolyHost')
        

        self.setQuitOnLastWindowClosed(False)
        self.is_closing = False
        self.debug_mode = debug_mode
        self._needs_overlay_reset = False

        # Create the menu
        self.log.debug("Building menu...")
        self.set_style()
        self.menu = QMenu()
        self.menu.setStyleSheet("QMenu {icon-size: 64px;} QMenu::item {icon-size: 64px; background: transparent;}")

        self.status = QAction(get_icon("sync.svg"), "Waiting for PolyKybd...", parent=self)
        self.status.setToolTip("Press to pause connection")
        # noinspection PyUnresolvedReferences
        self.status.triggered.connect(self.pause)
        self.exit = QAction(get_icon("power.svg"), "Quit", parent=self)
        # noinspection PyUnresolvedReferences
        self.exit.triggered.connect(self.quit_app)
        self.support = QAction(get_icon("support.svg"), "Get Support", parent=self)
        # noinspection PyUnresolvedReferences
        self.support.triggered.connect(self.open_support)
        self.about = QAction(get_icon("home.svg"), "About", parent=self)
        # noinspection PyUnresolvedReferences
        self.about.triggered.connect(self.open_about)

        self.settings_dialog = QAction(get_icon("settings.svg"), "Settings...", parent=self)
        # noinspection PyUnresolvedReferences
        self.settings_dialog.triggered.connect(self.open_settings)

        self.log_dialog = QAction(get_icon("log.svg"), "Log file...", parent=self)
        # noinspection PyUnresolvedReferences
        self.log_dialog.triggered.connect(self.open_log)
        self.log_viewer = None

        self.last_update_msec = 0
        self.last_update_10min_task = PERIODIC_10MIN_CYCLE_MSEC * 2
        self.current_lang = None
        self.keeb_lang_menu = None
        self.debug_lang_menu = None

        self.unicode_cache = UnicodeCache()
        #self.reconnect()
        self.menu.addAction(self.status)
        self.add_supported_lang(self.menu)

        self.cmdMenu = CommandsSubMenu(self, self.keeb)
        self.cmdMenu.build_menu(self.menu)

        # TODO: enable/disable depending on MRU usage
        action = QAction(get_icon("overlays.svg"), "Send Shortcut Overlay...", parent=self)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.send_shortcuts)
        self.menu.addAction(action)

        self.layout_editor = QAction(get_icon("keyboard.svg"), "Configure Keymap", parent=self)
        # noinspection PyUnresolvedReferences
        self.layout_editor.triggered.connect(self.open_layout_editor)
        self.menu.addAction(self.layout_editor)
        self.menu.addAction(self.settings_dialog)
        self.menu.addAction(self.log_dialog)

        if debug_mode > 0:
            debug_menu = self.menu.addMenu(get_icon("info.svg"), "Debugging")
            self.debug_lang_menu = debug_menu.addMenu(get_icon("language.svg"), "Change System Input Language")
            mru_action = QAction(get_icon("overlays.svg"), "Inspect MRU Cache...", parent=self)
            # noinspection PyUnresolvedReferences
            mru_action.triggered.connect(self.open_mru_inspector)
            debug_menu.addAction(mru_action)
            dump_action = QAction(get_icon("overlays.svg"), "Dump Mock Bitmaps...", parent=self)
            # noinspection PyUnresolvedReferences
            dump_action.triggered.connect(self.dump_mock_bitmaps)
            debug_menu.addAction(dump_action)

        self.menu.addAction(self.support)
        self.menu.addAction(self.about)
        self.menu.addAction(self.exit)

        self.log.debug("Create OS dependent input helper...")
        self.helper = None
        if platform.system() == "Windows":
            self.helper = WindowsInputHelper(self.poly_settings)
        elif platform.system() == "Linux":
            if IS_PLASMA:
                self.helper = LinuxPlasmaHelper()
            else:
                self.helper = LinuxGnomeInputHelper()
        elif platform.system() == "Darwin":
            self.helper = MacOSInputHelper()

        if not self.helper:
            self.log.error("Unsupported OS! Exiting...")
            sys.exit(-1)

        entries = self.helper.get_languages()

        result, info = self.helper.get_current_language()
        if result:
            self.log.info("Current System Language: %s", info)
            self.current_lang = info
        else:
            self.icon_manager.set_warning("System language query not supported for this platform.", 5000)
            self.log.warning("System language query not supported for this platform: '%s'", info)

        if debug_mode>0:
            for e in entries:
                self.log.info(" - Enumerating input language %s", e)
                self.debug_lang_menu.addAction(e, self.change_system_language)

        self.managed_connection_status()
        
        self.log.debug("Display tray...")
        # Add the menu to the tray
        # self.tray.activated.connect(self.on_activated)
        self.tray.setContextMenu(self.menu)
        self.tray.show()

        self.log.debug("Read overlay mapping file...")
        self.mapping = {}
        self.read_overlay_mapping_file(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/overlay-mapping.poly.yaml"))
        self.overlay_handler = OverlayHandler(self.mapping)

        self.log.debug("Get sunlight data...")
        self.sunlight = Sunlight(self.poly_settings.get("brightness_allow_online_location_lookup"), self.poly_settings.get("brightness_allow_online_irradiance_request"))
        
        self.log.debug("Starting cyclic checks...")
        self.reconnect()
        QTimer.singleShot(UPDATE_CYCLE_MSEC * 2, self.active_window_reporter)
 

    def set_style(self):
        self.setStyle("Fusion")
        # Now use a palette to switch to dark colors:
        palette = QPalette()
        base_color = QColor(35, 35, 35)
        window_base_color = QColor(80, 80, 80)
        text_color = QColor(200, 200, 200)
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
        
    # def on_activated(self, i_reason):
    #     if i_reason == QSystemTrayIcon.Trigger:
    #         if not self.menu.isVisible():
    #             self.menu.popup(QCursor.pos())
    #         else:
    #             self.menu.hide()

    def managed_connection_status(self):
        for action in self.menu.actions():
            action.setEnabled(self.connected and not self.paused)
        self.log_dialog.setEnabled(True)
        self.layout_editor.setEnabled(True)
        self.settings_dialog.setEnabled(True)
        self.status.setEnabled(True)
        self.support.setEnabled(True)
        self.about.setEnabled(True)
        self.exit.setEnabled(True)
        if self.connected:
            self.icon_manager.set_connected()
        else:
            self.icon_manager.set_disconnected()

    def show_mb(self, title, msg, result=False):
        if not result:
            if self.connected:
                mbox = QMessageBox()
                mbox.setWindowTitle(title)
                mbox.setText(msg)
                mbox.setIcon(QMessageBox.Warning if title == "Error" else QMessageBox.Information)
                mbox.exec_()
            else:
                self.log.warning("%s: %s", title, msg)

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
            connected_now = False
            response = ""
            if self.keeb.connect():
                connected_now, response = self.keeb.query_current_lang()
            if connected_now != self.connected:
                self.connected, msg = self.keeb.query_version_info()
                if self.connected:
                    kb_version = self.keeb.get_sw_version()
                    self.kb_sw_version = self.keeb.get_sw_version_number()
                    expected = __version__
                    if kb_version.startswith(expected[:3]):
                        if kb_version != expected:
                            self.log.warning("Warning! Minor version mismatch, expected '%s', got '%s'.", expected, kb_version)
                            self.status.setIcon(get_icon("sync_problem.svg"))
                            self.status.setText(
                                f"PolyKybd {self.keeb.get_name()} {self.keeb.get_hw_version()} ({kb_version}, please update to {expected}!)")
                        else:
                            self.status.setIcon(get_icon("sync.svg"))
                            self.status.setText(
                                f"PolyKybd {self.keeb.get_name()} {self.keeb.get_hw_version()} ({kb_version})")
                        if connected_now and self.poly_settings.get("unicode_send_composition_mode"):
                            mode = get_input_method()
                            self.log.info("Setting unicode mode to str %s", mode)
                            self.keeb.set_unicode_mode(mode)
                            self.update_ui_on_lang_change(response)
                        self.device_mgr.reset_all_caches()
                        self.overlay_handler.force_resend()
                        self._needs_overlay_reset = True
                        self.log.info("Connected: active window resend queued.")
                    else:
                        self.status.setIcon(get_icon("sync_disabled.svg"))
                        self.status.setText(f"Incompatible version: {msg}, expected {expected}, got {kb_version}'.")
                        self.connected = False
                else:
                    self.status.setIcon(get_icon("sync_disabled.svg"))
                    self.status.setText(msg)
            self.managed_connection_status()
            if connected_now:
                return response
            self.log.warning("Reconnect failed: '%s'", response if response else "NO RESPONSE")
        return self.current_lang

    @staticmethod
    def langcode_to_flag(lang_code):
        result = ""
        for ch in lang_code:
            num = 0x1F1E6 + ord(ch.upper()) - ord('A')
            result = f"{result}{chr(num)}"
        return result

    def add_supported_lang(self, menu):
        result, msg = self.keeb.enumerate_lang()
        if result:
            self.current_lang = self.keeb.get_current_lang()
            self.keeb_lang_menu = menu.addMenu(get_icon("language.svg"), f"Selected Language: {self.current_lang[:2]} {self.langcode_to_flag(self.current_lang[2:])}")

            all_languages = sorted(self.keeb.get_lang_list(), key=sort_by_country_abc)
            self.log.debug("Adding %s to language menu", all_languages)
            for lang in all_languages:
                text = f"{lang[:2]} {lang[2:].upper()}"
                if lang == self.current_lang:
                    text = f"{text} {chr(0x2714)}"
                item = self.keeb_lang_menu.addAction(text, self.change_keeb_language)
                item.setData(lang)
                icon = self.unicode_cache.get_icon_for(lang[2:])
                item.setIcon(icon)
        else:
            self.log.warning("Enumerating PolyKybd languages failed with '%s'", msg)

    def update_ui_on_lang_change(self, new_lang):
        if self.keeb_lang_menu:
            self.keeb_lang_menu.setTitle(f"Selected Language: {new_lang[:2]} {self.langcode_to_flag(new_lang[2:])}")
            for action in self.keeb_lang_menu.actions():
                lang = action.data()
                text = f"{lang[:2]} {self.langcode_to_flag(lang[2:])}"
                if lang == new_lang:
                    text = f"{text} {chr(0x2714)}"
                action.setText(text)

    def open_layout_editor(self):
        #webbrowser.open("https://usevia.app", new=0, autoraise=True)
        self.layout_dialog = KbLayoutDialog(self.keeb, self.device_settings)
        self.layout_dialog.show()

    def open_settings(self):
        dlg = SettingsDialog()
        dlg.setup(self.poly_settings.get_all(), self.debug_mode)
        if dlg.exec_() == QDialog.Accepted:
            self.poly_settings.set_all(dlg.get_updated_settings())
        dlg.close()

    def open_log(self):
        # assignment is needed otherwise the dialog would go away immediately
        delta = time.perf_counter()
        self.log_viewer = LogViewerDialog({"PolyHost Log": "host_log.txt", "PolyKybd Console Log": "polykybd_console.txt"})
        self.log_viewer.show()
        delta = time.perf_counter() - delta
        self.log.info("Opened log dialog in '%f' sec", delta)

    def open_mru_inspector(self):
        from polyhost.gui.mru_inspector_dialog import MRUInspectorDialog
        caches = [(e.name, e.cache) for e in self.device_mgr.all_entries if e.cache is not None]
        if not caches:
            QMessageBox.information(None, "MRU Cache", "MRU cache is not active (device not connected or MRU mode disabled).")
            return
        dlg = MRUInspectorDialog(caches, self.device_settings)
        dlg.exec_()

    def dump_mock_bitmaps(self):
        import subprocess
        import tempfile
        import numpy as np

        mock_entry = next((e for e in self.device_mgr.all_entries if not e.is_primary), None)
        if mock_entry is None:
            QMessageBox.information(None, "Mock Dump", "No mock device active.\nEnable dev_mock_enabled in settings.")
            return

        store = mock_entry.device._sim._store
        if not store:
            QMessageBox.information(None, "Mock Dump", "Mock has no stored bitmaps yet.\nSwitch to an app to trigger an overlay send.")
            return

        out_dir = tempfile.mkdtemp(prefix="polykybd_mock_")
        from polyhost.device.overlay_sim import _write_png_gray8
        for pool_slot, bitmap in sorted(store.items()):
            keycode_slot = pool_slot % 90
            modifier_var = pool_slot // 90
            if keycode_slot < 80:
                kc = keycode_slot + 0x04        # KC_A base
            elif keycode_slot < 82:
                kc = keycode_slot - 80 + 0x64   # KC_NONUS_BACKSLASH base
            else:
                kc = keycode_slot - 82 + 0xE0   # KC_LEFT_CTRL base
            fname = f"slot{pool_slot:03d}_kc0x{kc:02x}_mod{modifier_var}.png"
            bits = np.unpackbits(np.frombuffer(bitmap, dtype=np.uint8))
            pixels = (bits[:40 * 72].reshape(40, 72) * 255).astype(np.uint8)
            _write_png_gray8(os.path.join(out_dir, fname), pixels)

        self.log.info("Mock bitmaps dumped to %s", out_dir)
        if platform.system() == "Windows":
            os.startfile(out_dir)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", out_dir])
        else:
            subprocess.Popen(["xdg-open", out_dir])
        QMessageBox.information(None, "Mock Dump", f"Saved {len(store)} bitmaps to:\n{out_dir}")

    @staticmethod
    def open_support():
        webbrowser.open("https://discord.gg/gW8JescH7M", new=0, autoraise=True)

    @staticmethod
    def open_about():
        webbrowser.open("https://ko-fi.com/polykb", new=0, autoraise=True)

    def send_shortcuts(self):
        file_name = QFileDialog.getOpenFileName(None, 'Open file', '', "Image files (*.jpg *.gif *.png *.bmp *.jpeg)")
        if file_name[0]:
            for entry in self.device_mgr.all_entries:
                entry.device.send_overlays([file_name[0]])
        else:
            self.log.info("No file selected. Operation canceled.")

    def change_system_language(self):
        self.icon_manager.set_thinking()
        
        requested_lang = self.sender().text()
        lang, country = get_lang_and_country(requested_lang)
        result, output = self.helper.set_language(lang, country)
        if not result:
            msg = f"Changing input language to '{requested_lang}' failed with:\n\"{output}\""
            self.icon_manager.set_warning(msg)
            self.show_mb("Error", msg)
        else:
            self.log.info("Change input language to '%s'.", requested_lang)
        
        self.icon_manager.set_idle()

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
        self.icon_manager.set_disconnected()
        self.is_closing = True
        self.overlay_handler.close()
        self.quit()

    # noinspection PyPep8Naming
    def closeEvent(self, _):
        self.cmdMenu.disable_overlays()

    def send_overlay_data(self, data):
        files = []
        if isinstance(data, str):
            files.append(get_overlay_path(data))
        else:
            for overlay in data:
                files.append(get_overlay_path(overlay))

        if len(files) > 0:
            try:
                mru_enabled = self.poly_settings.get("overlay_mru_cache_enabled")
                mock_mru_enabled = self.poly_settings.get("dev_mock_overlay_mru_cache_enabled")
                for entry in self.device_mgr.all_entries:
                    use_mru = entry.cache is not None and (
                        (entry.is_primary and mru_enabled) or
                        (not entry.is_primary and mock_mru_enabled)
                    )
                    if use_mru:
                        entry.device.send_overlays_mru(files, entry.cache)
                    elif entry.is_primary:
                        self.cmdMenu.reset_overlays_and_usage()
                        entry.device.send_overlays(files)
                    else:
                        entry.device.reset_overlays_and_usage()
                        entry.device.send_overlays(files)
            except Exception as e:
                msg = f"Failed to send overlays '{files}': {e}"
                self.icon_manager.set_warning(msg, 5000)
                self.log.warning(msg)

            self.keeb.set_idle(False)

    def active_window_reporter(self):
        self.last_update_msec += UPDATE_CYCLE_MSEC
        self.last_update_10min_task += UPDATE_CYCLE_MSEC
        kb_lang = None
        if self.last_update_msec >= RECONNECT_CYCLE_MSEC:
            kb_lang = self.reconnect()
            self.last_update_msec = 0
            self.icon_manager.update()
        if self.connected:
            if self._needs_overlay_reset:
                self._needs_overlay_reset = False
                self.cmdMenu.reset_overlays_and_usage()
                self.log.info("Connected: overlay state cleared.")
            if self.keeb.pop_fresh_boot():
                self.device_mgr.reset_all_caches()
                self.log.info("Firmware restart detected — overlay MRU cache reset.")
            # limit the time frame
            self.last_update_msec = min(
                self.last_update_msec, RECONNECT_CYCLE_MSEC * 2)
            if kb_lang and self.current_lang != kb_lang:
                self.icon_manager.set_thinking()

                lang, country = get_lang_and_country(kb_lang)
                success, msg = self.helper.set_language(lang, country)
                if success:
                    data = self.overlay_handler.get_overlay_data()
                    if data:
                        self.send_overlay_data(data)
                else:
                    warning = f"Could not change OS language {kb_lang}."
                    self.icon_manager.set_warning(warning , 5000)
                    self.log.warning("%s (%s)", warning, msg)
                self.current_lang = kb_lang

                self.icon_manager.set_idle()

            data, cmd = self.overlay_handler.handle_active_window(
                UPDATE_CYCLE_MSEC, NEW_WINDOW_ACCEPT_TIME_MSEC)
            if cmd == OverlayCommand.DISABLE:
                for entry in self.device_mgr.all_entries:
                    entry.device.disable_overlays()
            elif cmd == OverlayCommand.ENABLE:
                for entry in self.device_mgr.all_entries:
                    entry.device.enable_overlays()

            if data and cmd == OverlayCommand.OFF_ON:
                self.icon_manager.set_thinking()
                self.send_overlay_data(data)
                self.icon_manager.set_idle()

            if self.last_update_10min_task > PERIODIC_10MIN_CYCLE_MSEC:
                self.last_update_10min_task = 0
                self.execute_10min_task()
        elif self.poly_settings.get("dev_run_window_detection_if_not_connected_to_poly_kybd"):
            self.overlay_handler.handle_active_window(UPDATE_CYCLE_MSEC, NEW_WINDOW_ACCEPT_TIME_MSEC)

        kb_serial = self.keeb.read_serial()
        if kb_serial:
            self.log.info("Received serial communication: %s", kb_serial)

        kb_log = self.keeb.get_console_output()
        if kb_log:
            self.keeb_log.info(kb_log)

        if not self.is_closing:
            QTimer.singleShot(UPDATE_CYCLE_MSEC, self.active_window_reporter)
        # except Exception as e:
        #    self.log.warning("Failed to report active window: %s", e)

    def execute_10min_task(self):
        if self.poly_settings.get("brightness_set_daylight_dependent"):
            min_val = self.poly_settings.get("irradiance_min")
            max_val = self.poly_settings.get("irradiance_max")
            prescaler = self.poly_settings.get("irradiance_prescaler")
            brightness = self.sunlight.get_brightness_now(min_val, max_val, prescaler)
            self.keeb.set_brightness(2+brightness*48)
