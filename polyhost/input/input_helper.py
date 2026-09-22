"""Shared input-helper base: the OS language switch every platform inherits.

⚠️ **The cycling here is a KEYSTROKE, not an API call.** `set_language` presses
the OS's "next input language" shortcut and re-reads the current language until
it matches, because neither Windows nor GNOME offers a way to select a layout
outright from an unprivileged process. `Key.cmd` is the Super/Win key through
pynput, so the same press serves Win+Space and Super+Space. macOS and KDE both
override `set_language` entirely — they have a real selector
(`TISSelectInputSource`, `qdbus … setLayout`) and never cycle.
"""

import logging
import time

from pynput.keyboard import Key, Controller

from polyhost.lang.lang_compat import LangComp

#: How long to let the OS apply a switch before re-reading the current
#: language. ⚠️ This is not padding. The Windows read used to be a PowerShell
#: spawn — hundreds of milliseconds — which hid the need for it; reading the
#: foreground window's layout through Win32 returns instantly and can beat the
#: switch it is meant to observe. GNOME's gsettings read is a subprocess too,
#: so the wait costs it a little and protects it the same way.
_SWITCH_SETTLE_S = 0.15

def get_country_from_iso639(iso639string : str):
    return iso639string[:2]

def country_equal_iso639(iso639string1 : str, iso639string2 : str):
    return iso639string1[:2] == iso639string2[:2]

class InputHelper:
    def __init__(self, compat_platform=None):
        """`compat_platform` names the forced-layout compatibility map to load
        (`res/forced_country_match_<platform>.txt`), or None for a subclass
        that resolves layouts entirely on its own.

        ⚠️ **Pass it even when the subclass overrides `set_language`** — KDE
        and macOS both read `self.comp` from their own implementations. What
        the argument controls is which FILE, and the platforms do not share a
        vocabulary."""
        self.log = logging.getLogger('PolyHost')
        self.comp = LangComp(compat_platform) if compat_platform else None

    def get_languages(self):
        return []
    
    def get_current_language(self):
        return False, "Not implemented in base class InputHelper"
    
    def set_language(self, lang, country):
        """Switch the OS input language, falling back to a compatible layout.

        ⚠️ **The fallback is what makes ~60 of the 156 PolyKybd layouts work at
        all.** Tahitian, Filipino, Swahili, Quechua, Basque — no OS installs a
        keyboard language for any of them, so the direct attempt below reports
        "No compatible language" and that is the end of it. The compatibility
        map says which installed layout actually types them.

        ⚠️ **An alternative the OS does not have costs no keypresses**, which
        is why there is no installed-check here: `_set_language_direct` returns
        before touching the controller when nothing installed shares the
        language. A second filter in this loop looked prudent and was dead
        code — it could only ever refuse what the callee already refuses."""
        ok, msg = self._set_language_direct(lang, country)
        if ok or self.comp is None:
            return ok, msg

        for tag in self.comp.get_compatible_lang_list(country) or ():
            alt_lang, _, alt_country = (tag or "").partition("-")
            if not alt_lang or (alt_lang == lang and alt_country.upper() == country.upper()):
                continue
            ok, alt_msg = self._set_language_direct(alt_lang, alt_country.upper())
            if ok:
                self.log.debug("Fell back to compatible layout %s for %s-%s",
                               alt_msg, lang, country)
                return True, alt_msg
        return False, msg

    def _set_language_direct(self, lang, country):
        """Cycle the OS to this exact language, with no compatibility fallback."""
        iso639_langs = self.get_languages()
        quick_cmp = False
        iso639 = f"{lang}-{country}"
        if iso639 not in iso639_langs:
            for lang_codes in iso639_langs:
                if lang == get_country_from_iso639(lang_codes):
                    quick_cmp = True
                    break
            if not quick_cmp:
                return False, f"No compatible language for {iso639} in {iso639_langs}"
        num_langs = len(iso639_langs)
        success, sys_lang_iso639 = self.get_current_language()

        controller = Controller()
        seen = [sys_lang_iso639]
        while success and num_langs>0:
            self.log.debug("Comparing: %s with %s", sys_lang_iso639, iso639)
            if iso639 == sys_lang_iso639:
                return True, iso639
            if quick_cmp and country_equal_iso639(iso639, sys_lang_iso639):
                return True, sys_lang_iso639
            controller.press(Key.cmd)
            controller.press(Key.space)
            controller.release(Key.cmd)
            controller.release(Key.space)

            time.sleep(_SWITCH_SETTLE_S)
            success, sys_lang_iso639 = self.get_current_language()
            seen.append(sys_lang_iso639)
            num_langs -= 1

        # ⚠️ Say WHICH failure this was. "Could not switch language to ko-KR"
        # is true of two completely different faults, and the field report
        # that exposed the stale Windows read could not tell them apart: the
        # switch had actually worked and only the observation was broken.
        # A current language that never moves across N presses means the
        # keystroke is not landing or the read is stale — never that the
        # target is missing, which the membership check above already ruled
        # out.
        if len(set(seen)) == 1:
            return False, (f"Could not switch language to {iso639}: the OS stayed "
                           f"on {seen[0]} through {len(seen) - 1} switch attempts "
                           f"(the keystroke is not landing, or the current-language "
                           f"read is stale)")
        return False, (f"Could not switch language to {iso639} "
                       f"(cycled through {' -> '.join(seen)})")
