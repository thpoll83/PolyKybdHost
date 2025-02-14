import subprocess


class LinuxXInputHelper():
    def getLanguages(self):
        result = subprocess.run(['setxkbmap', '-query'], stdout=subprocess.PIPE)
        entries = iter(result.stdout.splitlines())
        for e in entries:
            e = str(e, encoding='utf-8')
            if e.startswith('layout:'):
                return e.split(":")[-1].strip().split(",")
        return []

    def getAllLanguages(self):
        result = subprocess.run(['localectl', 'list-x11-keymap-layouts'], stdout=subprocess.PIPE)
        return iter(str(result.stdout, encoding='utf-8').splitlines())

    def setLanguage(self, lang):
        result = subprocess.run(['setxkbmap', lang], stdout=subprocess.PIPE)
        output = str(result.stdout, encoding='utf-8')
        if output != "b''":
            return output
        return ""
    
    def getCurrentLanguage(self):
        False, "Not Implemented" 
