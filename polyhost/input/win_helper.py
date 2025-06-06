import logging
import subprocess
from polyhost.input.input_helper import InputHelper

class WindowsInputHelper(InputHelper):
    def __init__(self):
        self.log = logging.getLogger('PolyHost')
        self.list = None
        self.query = """$ScriptBlock = {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.InputLanguage]::CurrentInputLanguage
    }
    $Job = Start-Job -ScriptBlock $ScriptBlock
    $Null = Wait-Job -Job $Job
    $CurrentLanguage = Receive-Job -Job $Job
    Remove-Job -Job $Job
    $CurrentLanguage"""
    
    def get_languages(self):
        if not self.list:
            try:
                result = subprocess.run(['powershell', 'Get-WinUserLanguageList'], stdout=subprocess.PIPE, check=True)
                self.list = []
                entries = iter(result.stdout.splitlines())
                for e in entries:
                    try:
                        e = str(e, encoding='utf-8')
                    except UnicodeDecodeError:
                        e = str(e)
                    if e.startswith('LanguageTag'):
                        self.list.append(e.split(":")[-1].strip())
            except subprocess.CalledProcessError as ex:
                self.log.warning("Exception when running Get-WinUserLanguageList: %s", str(ex))
        return self.list

    def get_current_language(self):
        try:
            result = subprocess.run(['powershell', self.query], stdout=subprocess.PIPE, check=True)
            entries = iter(result.stdout.splitlines())
            for e in entries:
                try:
                    e = str(e, encoding='utf-8')
                except UnicodeDecodeError:
                    e = str(e)
                if e.startswith('Culture'):
                    return True, e.split(":")[-1].strip()
            return False, str(result.stdout)
        except subprocess.CalledProcessError as ex:
            self.log.warning("Exception when running script block: %s", str(ex))
            return False, str(ex)
