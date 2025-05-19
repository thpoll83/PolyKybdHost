import logging
import os
import ipaddress
import pathlib
import socket
import sys


from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon
from polyhost._version import __version__
from polyhost.handler.remote_window import TCP_PORT

IS_PLASMA = os.getenv("XDG_CURRENT_DESKTOP") == "KDE"

if not IS_PLASMA:
    import pywinctl as pwc
else:
    import polyhost.handler.kde_win_reporter as pwc

UPDATE_CYCLE_MSEC = 250
NEW_WINDOW_ACCEPT_TIME_MSEC = 1000


class PolyForwarder(QApplication):
    def __init__(self, log_level, host):
        super().__init__(sys.argv)
        self.host = host

        logging.basicConfig(
            level=log_level,
            format="[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(filename="forwarder_log.txt"),
                logging.StreamHandler(stream=sys.stdout),
            ],
        )
        self.log = logging.getLogger("PolyForwarder")

        self.setQuitOnLastWindowClosed(False)
        self.win = None
        self.prev_win = None
        self.is_closing = False
        self.title = None
        self.last_update_msec = 0

        # Create the icon
        icon = QIcon(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/icons/pcolor.png"))

        # Create the tray
        self.tray = QSystemTrayIcon(parent=self)
        self.tray.setIcon(icon)
        self.tray.setVisible(True)
        self.tray.setToolTip(f"({__version__}) Forwarding to {host}")

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

        QTimer.singleShot(1000, self.active_window_reporter)

    def send_to_host(self, handle, title, name):
        try:
            ip = ipaddress.ip_address(self.host)
        except ValueError:
            ip = socket.gethostbyname(self.host)
        except OSError as err:
            self.log.error("Could not resolve %s: %s", str(self.host), str(err))
            return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((str(ip), TCP_PORT))
            s.send(f"{handle};{name};{title}".encode("utf-8"))
            s.close()
            return True
        except socket.timeout as err:
            self.log.error("Connection timed out: %s", str(err))
        except ConnectionRefusedError as err:
            self.log.error("Connection refused: %s", str(err))
        except ConnectionAbortedError as err:
            self.log.error("Connection aborted: %s", str(err))
        except ConnectionResetError as err:
            self.log.error("Connection reset: %s", str(err))
        except ConnectionError as err:
            self.log.error("Connection error: %s", str(err))
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
                    self.send_to_host(win.getHandle(), self.title, app_name)
                    self.log.info("Active App: %s", app_name)
        elif self.win:
            self.log.info("No active window")
            self.win = None
            self.title = None
            self.send_to_host(0, "", "")

        if not self.is_closing:
            QTimer.singleShot(UPDATE_CYCLE_MSEC, self.active_window_reporter)
        else:
            self.log.info("No more active window reporting.")
