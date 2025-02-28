import subprocess

from pynput.keyboard import Key, Controller

class LinuxGnomeInputHelper():
    def getLanguages(self):
        result = subprocess.run(['gsettings', 'get', 'org.gnome.desktop.input-sources', 'mru-sources'], stdout=subprocess.PIPE)
        entries = iter(result.stdout.splitlines())
        for e in entries:
            e = str(e, encoding='utf-8')
            if e.startswith('[('):
                simplify = e.translate(str.maketrans('', '', "[('\" )]"))
                return simplify.split(",")[1::2]
                
        return []

    def getAllLanguages(self):
        result = subprocess.run(['localectl', 'list-x11-keymap-layouts'], stdout=subprocess.PIPE)
        return iter(str(result.stdout, encoding='utf-8').splitlines())

    def setLanguage(self, lang):
        available = self.getLanguages(self)
        short_comparison = False
        if lang not in available:
            for lang_codes in available:
                if lang[:2] == lang_codes[:2]:
                    short_comparison = True
                    break
            if not short_comparison:
                return False
        num_langs = len(available)
        success, sys_lang = self.getCurrentLanguage(self)

        controller = Controller()
        while success and num_langs>0:
            if lang == sys_lang or (short_comparison and lang[:2] == sys_lang[:2]):
                return True
            controller.press(Key.cmd)
            controller.press(Key.space)
            controller.release(Key.space)
            controller.release(Key.cmd)
            success, sys_lang = self.getCurrentLanguage(self)
            num_langs = num_langs - 1
            
        return False
    
    def getCurrentLanguage(self):
        langs = self.getLanguages(self)
        return len(langs)>0, langs[0]
