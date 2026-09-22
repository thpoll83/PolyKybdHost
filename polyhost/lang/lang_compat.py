import logging
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
        #: Which map this is. Recorded because macOS and Windows currently
        #: hold the SAME values, so nothing in the data distinguishes them —
        #: a helper wired to the wrong one would behave identically today and
        #: diverge silently the first time the files differ.
        self.platform = platform
        self.mapping = dict()
        self.log = logging.getLogger('PolyHost')
        path = os.path.join(pathlib.Path(__file__).parent.parent.resolve(),
                            "res", f"forced_country_match_{platform}.txt")
        # ⚠️ **`encoding="utf-8"` is REQUIRED, not tidiness.** Without it
        # Python decodes with the platform default, which on Windows is the
        # ANSI code page (cp1252 on a Western install) and NOT UTF-8. These
        # files carry em dashes, box-drawing rules and a ⚠️ in their comments,
        # and cp1252 has no mapping for byte 0x8f — the tail of that emoji's
        # variation selector — so the read raised UnicodeDecodeError and took
        # PolyHost's constructor, the tray AND the daemon down with it
        # (field, Windows 11 / Python 3.13, 2026-09-22).
        #
        # ⚠️ The crash was the LUCKY outcome. The Linux and macOS maps contain
        # no byte cp1252 leaves undefined, so they decode to MOJIBAKE instead
        # of raising — harmless today only because every non-ASCII character
        # sits in a comment. A non-ASCII character in a VALUE would silently
        # resolve to the wrong layout.
        #
        # This went unnoticed because `LangComp` had only ever been built by
        # the two Linux helpers, where the default is UTF-8; wiring it into
        # Windows is what first ran this line there.
        try:
            with open(path, encoding="utf-8") as file:
                lines = file.readlines()
        except (OSError, UnicodeDecodeError) as ex:
            # A compatibility map is a FALLBACK. Losing it costs the folds for
            # ~60 of the 156 layouts; it must never cost the whole app, which
            # is what an exception here does — `PolyHost.__init__` builds the
            # input helper, so this raised straight out of startup.
            self.log.warning("Could not read the %s layout compatibility map "
                             "(%s: %s); continuing without folds.",
                             platform, type(ex).__name__, ex)
            return
        for line in lines:
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
