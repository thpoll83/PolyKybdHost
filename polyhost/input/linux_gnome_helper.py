import logging
import subprocess
from pynput.keyboard import Key, Controller

from polyhost.input.input_helper import InputHelper
from polyhost.lang.lang_compat import LangComp


class LinuxGnomeInputHelper(InputHelper):
    def __init__(self):
        self.log = logging.getLogger('PolyHost')
        self.comp = LangComp()
        self.list = None

    def get_languages(self):
        if not self.list:
            try:
                result = subprocess.run(['gsettings', 'get', 'org.gnome.desktop.input-sources', 'mru-sources'], stdout=subprocess.PIPE, check=True)
                entries = iter(result.stdout.splitlines())
                for e in entries:
                    e = str(e, encoding='utf-8')
                    if e.startswith('[('):
                        simplify = e.translate(str.maketrans('', '', "[('\" )]"))
                        self.list = simplify.split(",")[1::2]
                        return self.list
            except subprocess.CalledProcessError as ex:
                self.log.warning("Exception when running gsettings get: %s", str(ex))
        return self.list

    def get_all_languages(self):
        try:
            result = subprocess.run(['localectl', 'list-x11-keymap-layouts'], stdout=subprocess.PIPE, check=True)
            return iter(str(result.stdout, encoding='utf-8').splitlines())
        except subprocess.CalledProcessError as ex:
            self.log.warning("Exception when running localectl: %s", str(ex))
        return None
    
    def get_current_language(self):
        langs = self.get_languages()
        return len(langs)>0, langs[0]
