import os
import subprocess
import sys


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
        return os.system(f"powershell Set-WinUserLanguageList -LanguageList {lang} -Force")
