import subprocess
import re

lang_re = re.compile(r"^\s*\d+\) (.*)$")

class MacOSInputHelper:
    def get_languages(self):
        result = subprocess.run(['languagesetup', '-Localized'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        entries = iter(result.stdout.splitlines())
        languages = []
        for e in entries:
            e = str(e, encoding='utf-8')
            m = lang_re.match(e)
            if m:
                languages.append(m.group(1))
        return languages

    def set_language(self, lang):
        result = subprocess.run(['osascript', '-e', f"do shell script \"sudo languagesetup -langspec {lang}\" with administrator privileges"], stdout=subprocess.PIPE)
        output = str(result.stdout, encoding='utf-8')
        if not output.startswith(u"System Language set to:"):
            return False, output
        return True, lang
    
    def get_current_language(self):
        False, "Not Implemented" 
