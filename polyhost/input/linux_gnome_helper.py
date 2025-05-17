import subprocess

from pynput.keyboard import Key, Controller

from polyhost.lang.lang_compat import LangComp


class LinuxGnomeInputHelper:
    def __init__(self):
        self.comp = LangComp()

    def get_languages(self):
        result = subprocess.run(['gsettings', 'get', 'org.gnome.desktop.input-sources', 'mru-sources'], stdout=subprocess.PIPE)
        entries = iter(result.stdout.splitlines())
        for e in entries:
            e = str(e, encoding='utf-8')
            if e.startswith('[('):
                simplify = e.translate(str.maketrans('', '', "[('\" )]"))
                return simplify.split(",")[1::2]
                
        return []

    def get_all_languages(self):
        result = subprocess.run(['localectl', 'list-x11-keymap-layouts'], stdout=subprocess.PIPE)
        return iter(str(result.stdout, encoding='utf-8').splitlines())

    def set_language(self, lang):
        available = self.get_languages()
        short_comparison = False
        if lang not in available:
            for lang_codes in available:
                if lang[:2] == lang_codes[:2]:
                    short_comparison = True
                    break
            if not short_comparison:
                return False
        num_langs = len(available)
        success, sys_lang = self.get_current_language()

        controller = Controller()
        while success and num_langs>0:
            if lang == sys_lang or (short_comparison and lang[:2] == sys_lang[:2]):
                return True
            controller.press(Key.cmd)
            controller.press(Key.space)
            controller.release(Key.space)
            controller.release(Key.cmd)
            success, sys_lang = self.get_current_language()
            num_langs = num_langs - 1
            
        return False
    
    def get_current_language(self):
        langs = self.get_languages()
        return len(langs)>0, langs[0]
