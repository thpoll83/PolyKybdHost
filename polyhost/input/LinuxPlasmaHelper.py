import subprocess
from pathlib import Path


class LinuxPlasmaHelper():
    # [Layout]
    # DisplayNames=,,
    # LayoutList=kr,us,at
    # Use=true
    # VariantList=kr104,,
    def getLanguages(self):
        with open(Path.home() / ".config" / "kxkbrc", "r") as file:
            for line in file:
                stripped = line.strip()
                if stripped.startswith("LayoutList"):
                    return stripped.split("=, ")[1:]

    def getAllLanguages(self):
        return self.getLanguages()

    def setLanguage(self, lang):
        if not self.list:
            self.list = self.getLanguages()
        idx = self.list.index(lang)
        result = subprocess.run(
            ["qdbus", "org.kde.keyboard", "/Layouts", "setLayout", idx],
            stdout=subprocess.PIPE,
        )
        output = str(result.stdout, encoding="utf-8")
        if output != "true":
            return output
        return ""
    
    def getCurrentLanguage(self):
        False, "Not Implemented" 
