import os
import sys
import webbrowser
import hid
import subprocess
import platform

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QDialog, QSystemTrayIcon, QMenu, QAction, QMessageBox

class WindowsInputHelper():
    def getLanguages(self):
        result = subprocess.run(['powershell', 'Get-WinUserLanguageList'], stdout=subprocess.PIPE)
        langCodes = []
        entries = iter(result.stdout.splitlines())
        for e in entries:
            e = str(e, encoding='utf-8')
            if e.startswith('LanguageTag'):
                langCodes.append(e.split(":")[-1].strip())
        return langCodes
        
    def setLanguage(self, lang):
        return os.system(f"powershell Set-WinUserLanguageList -LanguageList {lang} -Force")

class LinuxXInputHelper():
    def getLanguages(self):
        result = subprocess.run(['setxkbmap', '-query'], stdout=subprocess.PIPE)
        entries = iter(result.stdout.splitlines())
        for e in entries:
            e = str(e, encoding='utf-8')
            if e.startswith('layout:'):
                return e.split(":")[-1].strip().split(",")
        return []

    def getAllLanguages(self):
        result = subprocess.run(['localectl', 'list-x11-keymap-layouts'], stdout=subprocess.PIPE)
        return iter(str(result.stdout, encoding='utf-8').splitlines())
    
    def setLanguage(self, lang):
        result = subprocess.run(['setxkbmap', lang], stdout=subprocess.PIPE)
        output = str(result.stdout, encoding='utf-8')
        if output != "b''":
            return output
        return ""
        
            
class PolyKybdHost(QApplication):
    def __init__(self):
        super().__init__(sys.argv)
        self.setQuitOnLastWindowClosed(False)

        # Create the icon
        icon = QIcon(os.path.join(os.path.dirname(__file__), "pcolor.png"))
           
        # Create the tray
        tray = QSystemTrayIcon(parent=self)
        tray.setIcon(icon)
        tray.setVisible(True)

        # Create the menu
        menu = QMenu()
        
        action0 = QAction("HID Terminal", parent=self)
        action0.triggered.connect(self.open_hid_terminal)
        menu.addAction(action0)

        action1 = QAction("Configure Keymap (VIA)", parent=self)
        action1.triggered.connect(self.open_via)
        menu.addAction(action1)
        
        langMenu = menu.addMenu("Change Input Language")

        action2 = QAction("Get Support", parent=self)
        action2.triggered.connect(self.open_support)
        menu.addAction(action2)
        
        action3 = QAction("About", parent=self)
        action3.triggered.connect(self.open_about)
        menu.addAction(action3)

        quit = QAction("Quit", parent=self)
        quit.triggered.connect(self.quit)
        menu.addAction(quit)

        self.helper = None
        if platform.system() == "Windows":
            self.helper = WindowsInputHelper
        elif platform.system() == "Linux":
            self.helper = LinuxXInputHelper

        #result = subprocess.run(['localectl', 'list-x11-keymap-layouts'], stdout=subprocess.PIPE)
        #entries = iter(result.stdout.splitlines())
        entries = self.helper.getLanguages(self)

        for e in entries:
            print(f"Enumerating input language {e}")
            langMenu.addAction(e, self.change_language)
                
        # Add the menu to the tray
        tray.setContextMenu(menu)
        tray.show()
        
    def open_hid_terminal(self):
        dialog = QDialog(None)
        dialog.setWindowTitle("HID Terminal")
        dialog.exec_()
        dialog.show()
        
    def open_via(self):
        webbrowser.open("https://usevia.app", new=0, autoraise=True)
        
    def open_support(self):
        webbrowser.open("https://discord.gg/5eU48M79", new=0, autoraise=True)

    def open_about(self):
        webbrowser.open("https://ko-fi.com/polykb", new=0, autoraise=True)

    def change_language(self):
        lang = self.sender().text()
        output = self.helper.setLanguage(self, lang)
        if output:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText(f"Changing input language to '{lang}' failed with:\n\"{output}\"")
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()
        else:
            msg = QMessageBox()
            msg.setWindowTitle("Success")
            msg.setText(f"Change input language to '{lang}'.")
            msg.setIcon(QMessageBox.Information)
            msg.exec_()

if __name__ == '__main__':
    app = PolyKybdHost()
    print("Executing PolyKybd Host...")
    sys.exit(app.exec_())