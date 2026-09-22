import os
import pathlib


class LangComp:
    """The forced keyboard-layout compatibility map, for one platform.

    ⚠️ **One file per platform, and `platform` is deliberately REQUIRED.** The
    question is the same everywhere -- "which OS layouts can also type the
    PolyKybd layout for country X" -- but the ANSWER is written in the
    vocabulary that platform matches on, and the two do not overlap: Linux
    names xkb layout codes (`ara`, `latam`, `gb`), macOS names the language
    tags its input sources report (`ar-SA`, `es-MX`, `en-GB`). A default here
    would hand whichever platform forgot to pass one a table of codes its
    matcher cannot resolve, and the symptom is a language quietly reporting no
    layout rather than an error."""

    def __init__(self, platform):
        self.mapping = dict()
        path = os.path.join(pathlib.Path(__file__).parent.parent.resolve(),
                            "res", f"forced_country_match_{platform}.txt")
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
        # Keys are stored lowercased; normalise the lookup too so a match does
        # not depend on the caller passing a lowercased country code.
        return bool(lang) and lang.lower() in self.mapping

    def get_compatible_lang_list(self, lang):
        if not lang:
            return None
        return self.mapping.get(lang.lower())
