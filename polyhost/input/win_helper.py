import ctypes
import locale
import logging
import subprocess
from polyhost.input.input_helper import InputHelper

#Get-WinUserLanguageList | ForEach-Object {
#    "$($_.LanguageTag): $($_.InputMethodTips -join ', ')"
#}

_WM_INPUTLANGCHANGEREQUEST = 0x0050
_KLF_ACTIVATE = 0x00000001


class WindowsInputHelper(InputHelper):
    def __init__(self, poly_settings=None):
        super().__init__()
        self.poly_settings = poly_settings
        self.list = None
        self.query = """$ScriptBlock = {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.InputLanguage]::CurrentInputLanguage
    }
    $Job = Start-Job -ScriptBlock $ScriptBlock
    $Null = Wait-Job -Job $Job
    $CurrentLanguage = Receive-Job -Job $Job
    Remove-Job -Job $Job
    $CurrentLanguage"""
    
    def get_languages(self):
        if not self.list:
            try:
                result = subprocess.run(['powershell', 'Get-WinUserLanguageList'], stdout=subprocess.PIPE, check=True)
                self.list = []
                entries = iter(result.stdout.splitlines())
                for e in entries:
                    try:
                        e = str(e, encoding='utf-8')
                    except UnicodeDecodeError:
                        e = str(e)
                    if e.startswith('LanguageTag'):
                        self.list.append(e.split(":")[-1].strip())
            except subprocess.CalledProcessError as ex:
                self.log.warning("Exception when running Get-WinUserLanguageList: %s", ex)
        return self.list

    def get_current_language(self):
        try:
            result = subprocess.run(['powershell', self.query], stdout=subprocess.PIPE, check=True)
            entries = iter(result.stdout.splitlines())
            for e in entries:
                try:
                    e = str(e, encoding='utf-8')
                except UnicodeDecodeError:
                    e = str(e)
                if e.startswith('Culture'):
                    return True, e.split(":")[-1].strip()
            return False, str(result.stdout)
        except subprocess.CalledProcessError as ex:
            msg = str(ex)
            self.log.warning("Exception when running script block: %s", msg)
            return False, msg

    def set_language(self, lang, country):
        if self.poly_settings and self.poly_settings.get("dev_win_native_set_language"):
            return self._set_language_native(lang, country)
        return super().set_language(lang, country)

    def _set_language_native(self, lang, country):
        """Experimental: switch input language via Win32 LoadKeyboardLayout + PostMessage."""
        iso639 = f"{lang}-{country}"

        # Find LCID from Python's locale table (maps int LCID -> "lang_COUNTRY")
        target = f"{lang}_{country}".lower()
        lcid = next(
            (lcid_val for lcid_val, loc in locale.windows_locale.items()
             if loc.lower() == target),
            None,
        )
        if lcid is None:
            return False, f"No LCID found for {iso639}"

        klid = f"{lcid:08x}"
        user32 = ctypes.windll.user32
        hkl = user32.LoadKeyboardLayoutW(klid, _KLF_ACTIVATE)
        if not hkl:
            return False, f"LoadKeyboardLayout failed for KLID {klid} ({iso639})"

        hwnd = user32.GetForegroundWindow()
        user32.PostMessageW(hwnd, _WM_INPUTLANGCHANGEREQUEST, 0, hkl)
        self.log.debug("Native set_language: KLID=%s HKL=%s hwnd=%s", klid, hkl, hwnd)
        return True, iso639

        # Alternative: ActivateKeyboardLayout via AttachThreadInput.
        # More reliable for apps that ignore WM_INPUTLANGCHANGEREQUEST, because it
        # directly switches the layout on the target thread's input queue rather than
        # sending a notification the app can choose not to act on.
        # Caution: AttachThreadInput can deadlock if the target thread is unresponsive;
        # always detach in a finally block.
        #
        # kernel32 = ctypes.windll.kernel32
        # hwnd = user32.GetForegroundWindow()
        # target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        # current_thread = kernel32.GetCurrentThreadId()
        # attached = user32.AttachThreadInput(current_thread, target_thread, True)
        # try:
        #     user32.ActivateKeyboardLayout(hkl, 0)
        # finally:
        #     if attached:
        #         user32.AttachThreadInput(current_thread, target_thread, False)
        # self.log.debug("Native set_language (ActivateKeyboardLayout): KLID=%s HKL=%s", klid, hkl)
        # return True, iso639
