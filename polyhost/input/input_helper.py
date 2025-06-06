from pynput.keyboard import Key, Controller

def get_country_from_iso639(iso639string : str):
    return iso639string[:2]

def country_equal_iso639(iso639string1 : str, iso639string2 : str):
    return iso639string1[:2] == iso639string2[:2]

class InputHelper:
    def get_languages(self):
        return []
    
    def get_current_language(self):
        return False, "Not implemented in base class InputHelper"
    
    def set_language(self, lang, country):
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
        while success and num_langs>0:
            if iso639 == sys_lang_iso639:
                return True, iso639
            if quick_cmp and country_equal_iso639(iso639, sys_lang_iso639):
                return True, sys_lang_iso639
            controller.press(Key.cmd)
            controller.press(Key.space)
            controller.release(Key.space)
            controller.release(Key.cmd)
            success, sys_lang_iso639 = self.get_current_language()
            num_langs = num_langs - 1
        
        return False, f"Could not switch language to {iso639}"