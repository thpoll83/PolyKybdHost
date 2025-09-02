import os
import pathlib


class LangComp:
    def __init__(self):
        self.mapping = dict()
        path = os.path.join(pathlib.Path(__file__).parent.parent.resolve(), "res", "forced_country_match.txt")
        with open(path) as file:
            for line in file.readlines():
                if "=" in line:
                    key, value = line.split('=')
                    key = key.strip(" \n\r")
                    self.mapping[key] = []
                    self.mapping[key].append(value.strip(" \n\r"))

    def has_compatible_lang(self, lang):
        return lang in self.mapping

    def get_compatible_lang_list(self, lang):
        if lang not in self.mapping:
            return None
        return self.mapping[lang]
