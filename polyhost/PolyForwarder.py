import logging
import os
import ipaddress
import socket
import sys


from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon
from _version import __version__

IS_PLASMA = os.getenv('XDG_CURRENT_DESKTOP')=="KDE"

if not IS_PLASMA:
    import pywinctl as pwc

class PolyForwarder(QApplication):
    def __init__(self, log_level, host):
        super().__init__(sys.argv)
        self.host = host

        logging.basicConfig(
            level=log_level,
            format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(filename='forwarder_log.txt'), logging.StreamHandler(stream=sys.stdout)]
        )
        self.log = logging.getLogger('PolyForwarder')

        self.setQuitOnLastWindowClosed(False)
        self.win = None
        self.isClosing = False

        # Create the icon
        icon = QIcon("polyhost/icons/pcolor.png")
           
        # Create the tray
        self.tray = QSystemTrayIcon(parent=self)
        self.tray.setIcon(icon)
        self.tray.setVisible(True)
        self.tray.setToolTip(f"({__version__}) Forwarding to {host}")

        self.tray.show()


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
    
    def sendToHost(self, handle, title, name):
        try:
            ip = ipaddress.ip_address(self.host)
        except ValueError:
            ip = socket.gethostbyname(self.host)
        except:
           self.log.error(f"Could not resolve {self.host}")
           return
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((str(ip), TCP_PORT))
            s.send(f"{handle};{name};{title}".encode("utf-8"))
            s.close()
        except socket.timeout as err:
            self.log.error(f"Connection timed out {err}")
        
    def activeWindowReporter(self):
        win = pwc.getActiveWindow()
        if win:
            if self.win is None or win.getHandle() != self.win.getHandle() or win.title != self.title:
                self.win = win
                self.title = win.title
                appName = self.win.getAppName()
                self.sendToHost(win.getHandle(), self.title, appName)
        elif self.win:
            self.log.info("No active window")
            self.win = None
            self.title = None
            self.sendToHost(0, "", "")

        if not self.isClosing:
            QTimer.singleShot(500, self.activeWindowReporter)
