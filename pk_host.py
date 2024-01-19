import os
import sys
import webbrowser
import hid
import subprocess
import platform
import HidHelper

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QDialog, QSystemTrayIcon, QMenu, QAction, QMessageBox, QVBoxLayout, QLabel

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
        
        #Conect t Keeb
        vid = 0x2021
        pid = 0x2007
        self.keeb = HidHelper.HidHelper(vid, pid)
        result = self.keeb.send_raw_report("P0".encode())
        
        if result == True:
            success, reply = self.keeb.read_raw_report(1000)
            if result:
                status = QAction(f"Connected to: {reply.decode()[3:]}", parent=self)
                menu.addAction(status)
                self.add_supported_lang(menu)
            else:
                status = QAction(f"Error: {reply}", parent=self)
                menu.addAction(status)
        else:
            status = QAction(f"Could not sent id: {result}", parent=self)
            menu.addAction(status)
        
        # action0 = QAction("HID Terminal", parent=self)
        # action0.triggered.connect(self.open_hid_terminal)
        # menu.addAction(action0)

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
    
    def add_supported_lang(self, menu):
        current_lang = "Unknown"
        result = self.keeb.send_raw_report("P1".encode())
        if result == True:
            success, reply = self.keeb.read_raw_report(100)
            if success:
                current_lang = reply.decode()[3:]
       
        result = self.keeb.send_raw_report("P2".encode())
        
        if result == True:
            success, reply = self.keeb.read_raw_report(100)
            reply = reply.decode()
            lang = ""
            while success and len(reply)>3:
                lang = f"{lang},{reply[3:]}"
                success, reply = self.keeb.read_raw_report(100)
                reply = reply.decode()
                
            lang_menu = menu.addMenu(f"Selected Language: {current_lang}")
            for l in lang.split(","):
                if l != "":
                    lang_menu.addAction(l, self.change_language)
            
    # def open_hid_terminal(self):   
    #     dialog = QDialog(None)
    #     dialog.setWindowTitle("HID Terminal")  
    #     layout = QVBoxLayout()
        
    #     data = "P2".encode() #[80, 50] #
    #     sent = keeb.send_raw_report(data)
    #     message = QLabel(f'Sent: {data}/{sent} Device manufacturer: {keeb.interface.manufacturer} product: {keeb.interface.product} Lang: {keeb.read_raw_report(1000)}')
    #     layout.addWidget(message)
    #     dialog.setLayout(layout)
    #     dialog.exec_()
    #     dialog.show()
        
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