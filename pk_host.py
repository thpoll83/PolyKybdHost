import os
import sys
import webbrowser
import time
from enum import Enum
import hid
import subprocess
import platform
import HidHelper
import ImageConverter
from bitstring import BitArray

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
        
class Cmd(Enum):
    GET_ID = 0
    GET_LANG = 1
    GET_LANG_LIST = 2
    CHANGE_LANG = 3
    SEND_OVERLAY = 4
    CLEAR_OVERLAYS = 5
    ENABLE_OVERLAYS = 6

def compose_cmd(cmd, extra1 = None, extra2 = None , extra3 = None):
    c = cmd.value + 30
    if extra3 != None:
        return bytearray.fromhex(f"09{c:02}3a{extra1:02x}{extra2:02x}{extra3:02x}")
    elif extra2 != None:
        return bytearray.fromhex(f"09{c:02}3a{extra1:02x}{extra2:02x}")
    elif extra1 != None:
        return bytearray.fromhex(f"09{c:02}3a{extra1:02x}")
    else:
        return bytearray.fromhex(f"09{c:02}")
    
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
        result = self.keeb.send_raw_report(compose_cmd(Cmd.GET_ID))
        
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

        action = QAction("Configure Keymap (VIA)", parent=self)
        action.triggered.connect(self.open_via)
        menu.addAction(action)
        
        langMenu = menu.addMenu("Change Input Language")

        action = QAction("Send Shortcut Overlay...", parent=self)
        action.triggered.connect(self.send_shortcuts)
        menu.addAction(action)
        
        action = QAction("Clear Shortcut Overlays", parent=self)
        action.triggered.connect(self.clear_overlays)
        menu.addAction(action)
        
        action = QAction("Enable Shortcut Overlays", parent=self)
        action.triggered.connect(self.enable_overlays)
        menu.addAction(action)
        
        action = QAction("Disable Shortcut Overlays", parent=self)
        action.triggered.connect(self.disable_overlays)
        menu.addAction(action)
        
        action = QAction("Get Support", parent=self)
        action.triggered.connect(self.open_support)
        menu.addAction(action)
        
        action = QAction("About", parent=self)
        action.triggered.connect(self.open_about)
        menu.addAction(action)

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
        result = self.keeb.send_raw_report(compose_cmd(Cmd.GET_LANG))
        if result == True:
            success, reply = self.keeb.read_raw_report(100)
            if success:
                current_lang = reply.decode()[3:]
       
        result = self.keeb.send_raw_report(compose_cmd(Cmd.GET_LANG_LIST))
        
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
                BYTES_PER_MSG = 24
                BYTES_PER_OVERLAY = int(72*40) / 8 # 360
                NUM_MSGS = int(BYTES_PER_OVERLAY/BYTES_PER_MSG) # 360/24 = 15
                #print(f"BYTES_PER_MSG: {BYTES_PER_MSG}, BYTES_PER_OVERLAY: {BYTES_PER_OVERLAY}, NUM_MSGS: {NUM_MSGS}")
                self.disable_overlays()
                for keycode in overlaymap:
                    bmp = overlaymap[keycode]
                    #sum = 0
                    #for i in range(0, 40):
                    #    bits = BitArray(bmp[i*9:(i+1)*9])
                    #    print(bits.bin + f". {len(bits.bin)}/{len(bits.bin)/8} {i}")
                    #    sum = sum + len(bits.bin)
                    #print(f"Bytes: {sum/8}")
                    
                    for i in range(0, NUM_MSGS):
                        mods = 0;
                        success = self.keeb.send_raw_report(compose_cmd(Cmd.SEND_OVERLAY, keycode, mods, i) + bmp[i*BYTES_PER_MSG:(i+1)*BYTES_PER_MSG])
                        if not success:
                            msg = QMessageBox()
                            msg.setWindowTitle("Error")
                            msg.setText(f"Error sending overlay message {i+1}/{NUM_MSGS}")
                            msg.setIcon(QMessageBox.Critical)
                            msg.exec_()
                            break
                all_keys = ", ".join(f"{key:#02x}" for key in overlaymap.keys())
                print(f"Overlays for keycodes {all_keys} have been sent.")
                self.enable_overlays()                             
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
            msg.setIcon(QMessageBox.Critical)
            msg.exec_()
        else:
            msg = QMessageBox()
            msg.setWindowTitle("Success")
            msg.setText(f"Change input language to '{lang}'.")
            msg.setIcon(QMessageBox.Information)
            msg.exec_()

    def clear_overlays(self):
        result = self.keeb.send_raw_report(compose_cmd(Cmd.CLEAR_OVERLAYS))
        if result == False:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText(f"Failed clearing overlays.")
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()
    
    def enable_overlays(self):
        result = self.keeb.send_raw_report(compose_cmd(Cmd.ENABLE_OVERLAYS, 1))
        if result == False:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText(f"Failed enabling overlays.")
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()
            
    def disable_overlays(self):
        result = self.keeb.send_raw_report(compose_cmd(Cmd.ENABLE_OVERLAYS, 0))
        if result == False:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText(f"Failed disabling overlays.")
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()
            
    def change_keeb_language(self):
        lang_index = self.sender().data()
        result = self.keeb.send_raw_report(compose_cmd(Cmd.CHANGE_LANG, lang_index))
        if result == True:
            success, reply = self.keeb.read_raw_report(100)
            if success:
                self.keeb_lang_menu.setTitle(f"Selected Language: {self.all_languages[lang_index]}")
            else:
                self.keeb_lang_menu.setTitle(f"Could not set {self.all_languages[lang_index]}: {reply}")
        else:
            self.keeb_lang_menu.setTitle(f"Could not send request ({request_string}): {reply}")
                
if __name__ == '__main__':
    app = PolyKybdHost()
    print("Executing PolyKybd Host...")
    sys.exit(app.exec_())