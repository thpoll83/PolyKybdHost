import ctypes
import locale
import subprocess
import sys
from polyhost.input.input_helper import InputHelper

# Under pythonw.exe (and any consoleless parent) Windows allocates a fresh
# console window for every child process unless CREATE_NO_WINDOW is passed.
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0

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
        # Query the current input language inline (no Start-Job, which would
        # spawn a grandchild powershell.exe whose console CREATE_NO_WINDOW can't
        # suppress). We emit a single explicit "Culture: <name>" line rather than
        # letting PowerShell default-format the InputLanguage object: the live
        # object renders as a TABLE (a "Culture  Handle  LayoutName" header + a
        # data row), and the parser matched the header — returning the literal
        # "Culture   Handle LayoutName" as the current language, so no comparison
        # ever matched and language switching always failed. Emitting the value
        # ourselves is formatting-independent (and locale-independent).
        self.query = (
            "Add-Type -AssemblyName System.Windows.Forms\n"
            "$lang = [System.Windows.Forms.InputLanguage]::CurrentInputLanguage\n"
            "if ($lang -and $lang.Culture) { 'Culture: ' + $lang.Culture.Name }")
    
    def get_languages(self):
        if not self.list:
            try:
                # Emit an explicit "LanguageTag: <tag>" line per language rather
                # than letting PowerShell default-format the list — with 2+
                # languages it renders as a TABLE whose header row also starts
                # with "LanguageTag" (and carries no value), the same formatting
                # trap that broke get_current_language. ForEach-Object is
                # formatting- and locale-independent.
                result = subprocess.run(
                    ['powershell', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden',
                     '-Command',
                     "Get-WinUserLanguageList | ForEach-Object { 'LanguageTag: ' + $_.LanguageTag }"],
                    stdout=subprocess.PIPE, creationflags=_CREATE_NO_WINDOW, check=True)
                self.list = self._parse_language_tags(result.stdout)
            except subprocess.CalledProcessError as ex:
                self.log.warning("Exception when running Get-WinUserLanguageList: %s", ex)
        return self.list

    @staticmethod
    def _parse_language_tags(stdout):
        """Collect the IETF tags from 'LanguageTag: <tag>' lines, ignoring a bare
        table header (no colon). Accepts bytes or str."""
        tags = []
        for raw in stdout.splitlines():
            try:
                line = raw if isinstance(raw, str) else str(raw, encoding='utf-8')
            except UnicodeDecodeError:
                line = str(raw)
            line = line.strip()
            if line.startswith('LanguageTag') and ':' in line:
                tags.append(line.split(':', 1)[1].strip())
        return tags

    def get_current_language(self):
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-NonInteractive', '-Sta', '-WindowStyle', 'Hidden',
                 '-Command', self.query],
                stdout=subprocess.PIPE, creationflags=_CREATE_NO_WINDOW, check=True)
            return self._parse_current_culture(result.stdout)
        except subprocess.CalledProcessError as ex:
            msg = str(ex)
            self.log.warning("Exception when running script block: %s", msg)
            return False, msg

    @staticmethod
    def _parse_current_culture(stdout):
        """Extract the IETF culture (e.g. 'en-US') from the query output.

        Matches a line starting with 'Culture' that carries a value after a
        colon — so the value line ('Culture: en-US') is read while a bare table
        HEADER ('Culture   Handle   LayoutName', no colon) is correctly ignored.
        Accepts bytes or str (subprocess stdout is bytes)."""
        for raw in stdout.splitlines():
            try:
                line = raw if isinstance(raw, str) else str(raw, encoding='utf-8')
            except UnicodeDecodeError:
                line = str(raw)
            line = line.strip()
            if line.startswith('Culture') and ':' in line:
                return True, line.split(':', 1)[1].strip()
        return False, str(stdout)

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
        if not hwnd:
            self.log.warning("Native set_language: no foreground window, falling back to pynput cycling")
            return super().set_language(lang, country)
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
