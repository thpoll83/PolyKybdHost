"""macOS input helper — selects the keyboard INPUT SOURCE.

⚠️ **This used to change the system UI language, which is a different thing.**
`set_language` ran ``sudo languagesetup -langspec xx-YY`` through osascript
*"with administrator privileges"*: a password dialog on every connect, applied
at the next login, and no effect at all on which keyboard layout types. A
language key on the PolyKybd means *"switch the input source"*, so it goes
through Text Input Source Services now — see
:mod:`polyhost.input.macos_input_source` for the bridge and its limits.

⚠️ **Everything here talks ONE namespace: the input source's own language
tag.** `get_current_language` used to answer the HIToolbox *"KeyboardLayout
Name"* (``"German"``), which can never equal the ``de-DE`` the caller compares
it against — so `PolyHost` believed the OS language differed on every single
probe and re-fired the switch (and, with the old implementation, the password
dialog) for the life of the process. Do not reintroduce a display name here."""

from polyhost.input import macos_input_source as tis
from polyhost.input.input_helper import InputHelper
from polyhost.lang.lang_compat import LangComp


class MacOSInputHelper(InputHelper):
    def __init__(self):
        super().__init__()   # sets self.log (the set_language/get_languages error paths use it)
        # The macOS half of the compatible-layout table the KDE helper also
        # consults, for the same reason: ~60 of the 156 PolyKybd layouts are
        # folds onto another country's layout and macOS has an input source
        # for none of those languages. The macOS file states its answers as
        # language tags, which is what this platform matches on; see
        # `pick_input_source` for why it is a fallback.
        self.comp = LangComp("macos")
        self.list = None

    def get_languages(self):
        """The language tags of the ENABLED input sources, deduplicated.

        Not every layout macOS ships: `TISSelectInputSource` can only select a
        source the user has enabled, so offering the rest would list languages
        that cannot be switched to."""
        if self.list is None:   # None = not queried yet; [] is a valid cached result
            sources, error = tis.list_input_sources()
            if error:
                self.log.warning("Could not enumerate macOS input sources: %s", error)
                return []
            tags = []
            for source in sources:
                tag = tis.tag_for_source(source)
                if tag and tag not in tags:
                    tags.append(tag)
            self.list = tags
        return self.list

    def get_current_language(self):
        source, error = tis.current_input_source()
        if error:
            return False, error
        tag = tis.tag_for_source(source)
        if not tag:
            return False, f"Input source {source.get('id')} reports no language"
        return True, tag

    def set_language(self, lang, country):
        """Select the enabled input source that matches the keyboard's language.

        Returns ``(False, reason)`` when no enabled source speaks it — naming
        the sources that were on offer, because the fix is in System Settings
        and not in the app."""
        sources, error = tis.list_input_sources()
        if error:
            self.log.warning("Could not enumerate macOS input sources: %s", error)
            return False, error

        wanted = tis.normalize_tag(lang, country)
        chosen = tis.pick_input_source(
            sources, lang, country, self.comp.get_compatible_lang_list(country))
        if chosen is None:
            available = ", ".join(
                f"{s.get('name') or s.get('id')} ({'/'.join(s.get('languages') or []) or '?'})"
                for s in sources)
            return False, (f"No enabled macOS input source for {wanted}. "
                           f"Enabled: {available or 'none'}")

        selected, error = tis.select_input_source(chosen["id"])
        if not selected:
            self.log.warning("Could not select macOS input source %s: %s",
                             chosen.get("id"), error)
            return False, error
        self.log.debug("Selected macOS input source %s (%s) for %s",
                       chosen.get("id"), chosen.get("name"), wanted)
        return True, tis.tag_for_source(chosen) or wanted
