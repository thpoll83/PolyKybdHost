import os
import sys
import webbrowser
import hid
import subprocess
import platform
import HidHelper
import ImageConverter

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QDialog, QSystemTrayIcon, QMenu, QAction, QMessageBox, QVBoxLayout, QLabel, QFileDialog

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
            status = QAction(f"Could not send id: {result}", parent=self)
            menu.addAction(status)

        action0 = QAction("Configure Keymap (VIA)", parent=self)
        action0.triggered.connect(self.open_via)
        menu.addAction(action0)
        
        langMenu = menu.addMenu("Change Input Language")

        action1 = QAction("Send Shortcut Overlay...", parent=self)
        action1.triggered.connect(self.send_shortcuts)
        menu.addAction(action1)
        
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
            all = ""
            while success and len(reply)>3:
                all = f"{all},{reply[3:]}"
                success, reply = self.keeb.read_raw_report(100)
                reply = reply.decode()
                
            self.keeb_lang_menu = menu.addMenu(f"Selected Language: {current_lang}")
            index = 0
            self.all_languages = list(filter(None, all.split(",")))
            for lang in self.all_languages:
                item = self.keeb_lang_menu.addAction(lang, self.change_keeb_language)
                item.setData(index)
                index = index + 1
            
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

    def send_shortcuts(self):
        fname = QFileDialog.getOpenFileName(None, 'Open file', '',"Image files (*.jpg *.gif *.png *.bmp *jpeg)")
        if len(fname)>0:
            conv = ImageConverter.ImageConverter(fname[0])
            overlaymap = conv.extract_overlays()
            
            if overlaymap == None:
                msg = QMessageBox()
                msg.setWindowTitle("Error")
                msg.setText("No overlays generated.")
                msg.setIcon(QMessageBox.Warning)
                msg.exec_()
            else:
                for keycode in overlaymap:
                    request_string = f"50343a{keycode:02}" #P4:KEYCODE
                    result = self.keeb.send_raw_report(bytearray.fromhex(request_string))
                    if result == True:
                        for i in (0, 12): #  (overlay size in px 72*40) / (px per byte 8) / (bytes per msg 32) = 11.25 -> 12 msgs
                            bmp = overlaymap[keycode]
                            end = (i+1)*32
                            if end>len(bmp):
                                end = len(bmp)
                            success = self.keeb.send_raw_report(bmp[i*32:end])
                            if not success:
                                msg = QMessageBox()
                                msg.setWindowTitle("Error")
                                msg.setText(f"Error overlay sending message {i}")
                                msg.setIcon(QMessageBox.Warning)
                                msg.exec_()
                                break
                    else:
                        msg = QMessageBox()
                        msg.setWindowTitle("Error")
                        msg.setText("No reply. Cannot send overlay sending messages.")
                        msg.setIcon(QMessageBox.Warning)
                        msg.exec_()
                        break
                                        
        else:
            msg = QMessageBox()
            msg.setWindowTitle("Info")
            msg.setText("No file selected. Operation canceled.")
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()       
        
        
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

    def change_keeb_language(self):
        index = self.sender().data()
        request_string = f"50333a{index:02}"
        request = bytearray.fromhex(request_string)
        result = self.keeb.send_raw_report(request)
        if result == True:
            success, reply = self.keeb.read_raw_report(100)
            if success:
                self.keeb_lang_menu.setTitle(f"Selected Language: {self.all_languages[index]}")
            else:
                self.keeb_lang_menu.setTitle(f"Could not set {self.all_languages[index]}: {reply}")
        else:
            self.keeb_lang_menu.setTitle(f"Could not send request ({request_string}): {reply}")
                
if __name__ == '__main__':
    app = PolyKybdHost()
    print("Executing PolyKybd Host...")
    #print(f"  Pillow version:{__PIL.__version__}")
    sys.exit(app.exec_())