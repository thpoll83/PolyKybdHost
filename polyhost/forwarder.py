import logging
from logging.handlers import RotatingFileHandler
import os
import ipaddress
import pathlib
import socket
import sys


from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon
from polyhost._version import __version__
from polyhost.gui.get_icon import get_icon
from polyhost.handler.remote_window import TCP_PORT

IS_PLASMA = os.getenv("XDG_CURRENT_DESKTOP") == "KDE"

if not IS_PLASMA:
    import pywinctl as pwc
else:
    import polyhost.handler.kde_win_reporter as pwc

UPDATE_CYCLE_MSEC = 250
NEW_WINDOW_ACCEPT_TIME_MSEC = 1000

# Define custom debug levels
DEBUG_DETAILED = 8   # Custom level below DEBUG (10)

logging.addLevelName(DEBUG_DETAILED, "DEBUG_DETAILED")

def debug_detailed(self, message, *args, **kwargs):
    if self.isEnabledFor(DEBUG_DETAILED):
        self._log(DEBUG_DETAILED, message, args, **kwargs)

logging.Logger.debug_detailed = debug_detailed

class PolyForwarder(QApplication):
    def __init__(self, log_level, host):
        super().__init__(sys.argv)
        self.host = host

        logging.basicConfig(
            level=log_level,
            format="[%(asctime)s] %(levelname)-7s {%(filename)s:%(lineno)d} - %(message)s",
            handlers=[
                RotatingFileHandler(
                    filename="forwarder_log.txt",
                    maxBytes=10 * 1024 * 1024,  # 10 MB
                    backupCount=3,
                    encoding="utf-8"
                ),
                logging.StreamHandler(stream=sys.stdout),
            ],
        )
        self.log = logging.getLogger("PolyForwarder")
        # Create the icon
        icon = get_icon("pgray.png")
        self.setWindowIcon(icon)
        # Create the tray
        self.tray = QSystemTrayIcon(parent=self)
        self.tray.setIcon(icon)
        self.tray.setVisible(True)
        self.tray.setToolTip(f"({__version__}) Forwarding to {host}")
        
        self.setQuitOnLastWindowClosed(False)
        self.win = None
        self.prev_win = None
        self.is_closing = False
        self.title = None
        self.last_update_msec = 0

        self.tray.show()

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
        palette.setColor(QPalette.Text, text_color)
        palette.setColor(QPalette.Button, window_base_color)
        palette.setColor(QPalette.ButtonText, text_color)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, highlight_text_color)
        self.setPalette(palette)

        # Create the icon
        icon = get_icon("pcolor.png")
        self.setWindowIcon(icon)
        self.tray.setIcon(icon)
        
        QTimer.singleShot(1000, self.active_window_reporter)

    def send_to_host(self, handle, title, name):
        try:
            ip = ipaddress.ip_address(self.host)
        except ValueError:
            ip = socket.gethostbyname(self.host)
        except OSError as err:
            self.log.error("Could not resolve %s: %s", self.host, err)
            return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((str(ip), TCP_PORT))
            s.send(f"{handle};{name};{title}".encode("utf-8"))
            s.close()
            return True
        except socket.timeout as err:
            self.log.error("Connection timed out: %s",err)
        except ConnectionRefusedError as err:
            self.log.error("Connection refused: %s", err)
        except ConnectionAbortedError as err:
            self.log.error("Connection aborted: %s", err)
        except ConnectionResetError as err:
            self.log.error("Connection reset: %s", err)
        except ConnectionError as err:
            self.log.error("Connection error: %s", err)
        return False

    def quit_app(self):
        self.is_closing = True
        self.quit()

    def active_window_reporter(self):
        self.last_update_msec += UPDATE_CYCLE_MSEC
        win = pwc.getActiveWindow()
        if win:
            if self.prev_win != win:
                self.prev_win = win
                self.last_update_msec = 0
            if self.last_update_msec > NEW_WINDOW_ACCEPT_TIME_MSEC:
                #just to limit the time value:
                self.last_update_msec = NEW_WINDOW_ACCEPT_TIME_MSEC * 2
                if (
                    self.win is None
                    or win.getHandle() != self.win.getHandle()
                    or win.title != self.title
                ):
                    self.win = win
                    self.title = win.title
                    app_name = self.win.getAppName()
                    handle = win.getHandle()
                    self.send_to_host(handle, self.title, app_name)
                    self.log.info("Active App: '%s' %s %d", self.title, app_name, handle)
        elif self.win:
            self.log.info("No active window")
            self.win = None
            self.title = None
            self.send_to_host(0, "", "")

        if not self.is_closing:
            QTimer.singleShot(UPDATE_CYCLE_MSEC, self.active_window_reporter)
        else:
            self.log.info("No more active window reporting.")
