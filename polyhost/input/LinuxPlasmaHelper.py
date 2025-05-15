import re
import subprocess
from pathlib import Path

from polyhost.lang.LangComp import LangComp


class LinuxPlasmaHelper():
    def __init__(self):
        self.comp = LangComp()
        self.list = None

    # [Layout]
    # DisplayNames=,,
    # LayoutList=kr,us,at
    # Use=true
    # VariantList=kr104,,
    def getLanguages(self):
        if not self.list:
            with open(Path.home() / ".config" / "kxkbrc", "r") as file:
                for line in file:
                    stripped = line.strip()
                    if stripped.startswith("LayoutList"):
                        self.list = re.split('[=, ]', stripped)[1:]
                        return self.list
        return self.list

    def getAllLanguages(self):
        return self.getLanguages()

    def setLanguage(self, lang):
        self.getLanguages()
        idx = None
        if lang in self.list:
            idx = self.list.index(lang)
        else:
            lang_code, country_code = lang.split('-')
            country_code = country_code.lower()
            if country_code in self.list:
                idx = self.list.index(country_code)
            elif lang_code in self.list:
                idx = self.list.index(lang_code)
            else:
                alternatives = self.comp.get_compatible_lang_list(country_code)
                if alternatives:
                    for alt_lang in alternatives:
                        if alt_lang in self.list:
                            idx = self.list.index(alt_lang)
                            break
                if not idx:
                    return False, f"Language {lang} not present on system: {self.list}"
        result = subprocess.run(
            ["qdbus", "org.kde.keyboard", "/Layouts", "setLayout", str(idx)],
            stdout=subprocess.PIPE,
        )
        output = str(result.stdout, encoding="utf-8")
        if output != "true\n":
            return False, output
        return True, lang
    
    def getCurrentLanguage(self):
        False, "Not Implemented" 
