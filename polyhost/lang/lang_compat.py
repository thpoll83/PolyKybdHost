import os
import pathlib


class LangComp:
    def __init__(self):
        self.mapping = dict()
        path = os.path.join(pathlib.Path(__file__).parent.parent.resolve(), "res", "forced_country_match.txt")
        with open(path) as file:
            for line in file.readlines():
                line = line.strip()
                # Skip blank lines and '#' comments; only "key=value" lines count.
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip(" \n\r").lower()
                if not key:
                    continue
                # Values may be comma-separated and/or repeated across lines with
                # the same key; accumulate (de-duplicated) instead of overwriting,
                # so one layout can list several compatible OS layouts.
                bucket = self.mapping.setdefault(key, [])
                for alt in value.split(","):
                    alt = alt.strip(" \n\r").lower()
                    if alt and alt not in bucket:
                        bucket.append(alt)

    def has_compatible_lang(self, lang):
        return lang in self.mapping

    def get_compatible_lang_list(self, lang):
        if lang not in self.mapping:
            return None
        return self.mapping[lang]
