import re
import subprocess
from pathlib import Path

from polyhost.input.input_helper import InputHelper
from polyhost.lang.lang_compat import LangComp


class LinuxPlasmaHelper(InputHelper):
    def __init__(self):
        self.comp = LangComp()
        self.list = None

    def get_languages(self):
        return self.get_countries()

    # [Layout]
    # DisplayNames=,,
    # LayoutList=kr,us,at
    # Use=true
    # VariantList=kr104,,
    def get_countries(self):
        if not self.list:
            with open(Path.home() / ".config" / "kxkbrc") as file:
                for line in file:
                    stripped = line.strip()
                    if stripped.startswith("LayoutList"):
                        self.list = re.split('[=, ]', stripped)[1:]
                        return self.list
        return self.list

    def get_all_languages(self):
        return self.get_countries()

    def set_language(self, lang, country):
        self.get_countries()
        idx = None
        iso639 = f"{lang}-{country}"
        if iso639 in self.list:
            idx = self.list.index(iso639)
        else:
            country = country.lower()
            if country in self.list:
                idx = self.list.index(country)
            elif lang in self.list:
                idx = self.list.index(lang)
            else:
                alternatives = self.comp.get_compatible_lang_list(country)
                if alternatives:
                    for alt_lang in alternatives:
                        if alt_lang in self.list:
                            idx = self.list.index(alt_lang)
                            break
                if not idx:
                    return False, f"Language {lang} not present on system: {self.list}"
        try:
            result = subprocess.run(
                ["qdbus", "org.kde.keyboard", "/Layouts", "setLayout", str(idx)],
                stdout=subprocess.PIPE,
                check=True,
            )
            output = str(result.stdout, encoding="utf-8")
            if output != "true\n":
                return False, output
            return True, lang
        except subprocess.CalledProcessError as ex:
            msg = str(ex)
            self.log.warning("Exception when running qdbus: %s", msg)
            return False, msg

    def get_current_language(self):
        self.get_countries()
        if not self.list:
            return False, "No layout list loaded"
        try:
            result = subprocess.run(
                ["qdbus", "org.kde.keyboard", "/Layouts", "getLayout"],
                stdout=subprocess.PIPE,
                check=True,
            )
            idx = int(result.stdout.strip())
            if 0 <= idx < len(self.list):
                return True, self.list[idx]
            return False, f"Layout index {idx} out of range ({len(self.list)} layouts)"
        except subprocess.CalledProcessError as ex:
            return False, str(ex)
        except ValueError as ex:
            return False, f"Unexpected qdbus output: {ex}"
