import os
import subprocess
from pynput.keyboard import Key, Controller

query = """$ScriptBlock = {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.InputLanguage]::CurrentInputLanguage
    }
    $Job = Start-Job -ScriptBlock $ScriptBlock
    $Null = Wait-Job -Job $Job
    $CurrentLanguage = Receive-Job -Job $Job
    Remove-Job -Job $Job
    $CurrentLanguage"""
        
class WindowsInputHelper():
    def getLanguages(self):
        result = subprocess.run(['powershell', 'Get-WinUserLanguageList'], stdout=subprocess.PIPE)
        langCodes = []
        entries = iter(result.stdout.splitlines())
        for e in entries:
            try:
                e = str(e, encoding='utf-8')
            except UnicodeDecodeError:
                e = str(e)
            if e.startswith('LanguageTag'):
                langCodes.append(e.split(":")[-1].strip())
        return langCodes

    def setLanguage(self, lang):
        available = self.getLanguages(self)
        short_comparison = False
        if lang not in available:
            for lang_codes in available:
                if lang[:2] == lang_codes[:2]:
                    short_comparison = True
                    break
            if not short_comparison:
                return False
        num_langs = len(available)
        success, sys_lang = self.getCurrentLanguage(self)

        controller = Controller()
        while success and num_langs>0:
            if lang == sys_lang or (short_comparison and lang[:2] == sys_lang[:2]):
                return True
            controller.press(Key.cmd)
            controller.press(Key.space)
            controller.release(Key.space)
            controller.release(Key.cmd)
            success, sys_lang = self.getCurrentLanguage(self)
            num_langs = num_langs - 1
            
        return False
    
    def getCurrentLanguage(self):
        result = subprocess.run(['powershell', query], stdout=subprocess.PIPE)
        entries = iter(result.stdout.splitlines())
        for e in entries:
            try:
                e = str(e, encoding='utf-8')
            except UnicodeDecodeError:
                e = str(e)
            if e.startswith('Culture'):
                return True, e.split(":")[-1].strip()
        return False, str(result.stdout)

        
