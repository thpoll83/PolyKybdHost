import logging
import subprocess
import re

lang_re = re.compile(r"^\s*\d+\) (.*)$")

class MacOSInputHelper:
    def __init__(self):
        self.log = logging.getLogger('PolyHost')
        self.list = None

    def get_languages(self):
        if not self.list:
            try:
                result = subprocess.run(
                    ["languagesetup", "-Localized"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    check=True,
                )
                entries = iter(result.stdout.splitlines())
                self.list = []
                for entry in entries:
                    entry = str(entry, encoding="utf-8")
                    m = lang_re.match(entry)
                    if m:
                        self.list.append(m.group(1))
            except subprocess.CalledProcessError as ex:
                self.log.warning("Exception when running languagesetup: %s", ex)
        return self.list

    def set_language(self, lang, country):
        try:
            iso639 = f"{lang}-{country}"
            param = f'do shell script "sudo languagesetup -langspec {iso639}" with administrator privileges'
            result = subprocess.run(
                ["osascript", "-e", param],
                stdout=subprocess.PIPE,
                check=True,
            )
            output = str(result.stdout, encoding="utf-8")
            if not output.startswith("System Language set to:"):
                return False, output
            return True, iso639
        except subprocess.CalledProcessError as ex:
            msg = str(ex)
            self.log.warning("Exception when running Get-WinUserLanguageList: %s", msg)
            return False, msg

    def get_current_language(self):
        False, "Not Implemented" 
