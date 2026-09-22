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
        super().__init__("windows")
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
        if self.list is None:   # None = not queried yet; [] is a valid cached result
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
        table header (no colon). Accepts bytes or str.

        The value after the colon is split on whitespace, so a single line that
        carries several tags is expanded into one entry per tag. Some Windows /
        PowerShell builds don't enumerate the WinUserLanguageList in the pipeline,
        so 'LanguageTag: ' + $_.LanguageTag member-enumerates the whole list and
        joins it with the default $OFS (a space) into one line
        ('LanguageTag: en-AT en-US de-AT'). Without the split that arrives as a
        single bogus tag 'en-AT en-US de-AT', which matches no language (field log
        2026-06-20) and shows as one entry in the debug language menu."""
        tags = []
        for raw in stdout.splitlines():
            try:
                line = raw if isinstance(raw, str) else str(raw, encoding='utf-8')
            except UnicodeDecodeError:
                line = str(raw)
            line = line.strip()
            if line.startswith('LanguageTag') and ':' in line:
                tags.extend(line.split(':', 1)[1].split())
        return tags

    def get_current_language(self):
        """The input language of the FOREGROUND WINDOW.

        ⚠️ **Asking a fresh PowerShell process was the wrong question.**
        `InputLanguage.CurrentInputLanguage` is per-THREAD, so a brand-new
        process reports the system default, not what the window in front is
        typing in. It therefore never followed a Win+Space switch: the field
        log shows the same `ko-KR` on eight consecutive reads across eight
        presses that were demonstrably landing (2026-09-22). `set_language`
        compares against this value to decide when to stop cycling, so a
        stuck read means it can never succeed — it presses N times, never
        sees the target, and reports failure for a switch that worked.

        `GetKeyboardLayout(<foreground thread>)` asks about the right thread.
        PowerShell stays as the fallback for the case that has no answer: no
        foreground window at all, which a headless or freshly-started process
        can genuinely hit."""
        ok, value = self._current_language_win32()
        if ok:
            return True, value
        self.log.debug("Win32 layout read unavailable (%s); using PowerShell", value)
        return self._current_language_powershell()

    def _current_language_win32(self):
        """`(True, "de-AT")` from the foreground window's keyboard layout."""
        try:
            user32 = ctypes.windll.user32
        except AttributeError as ex:      # not Windows
            return False, f"no user32 ({ex})"
        try:
            # Pin the signatures: HKL and HWND are pointer-sized, and the
            # default `int` restype truncates them on 64-bit.
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            user32.GetWindowThreadProcessId.restype = ctypes.c_uint32
            user32.GetKeyboardLayout.argtypes = [ctypes.c_uint32]
            user32.GetKeyboardLayout.restype = ctypes.c_void_p

            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                # ⚠️ Do NOT fall through to GetKeyboardLayout(0) here — thread
                # id 0 means "the calling thread", which is the very thing
                # that made the PowerShell answer useless.
                return False, "no foreground window"
            thread_id = user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), None)
            hkl = user32.GetKeyboardLayout(thread_id)
        except (AttributeError, OSError, ValueError) as ex:
            return False, f"{type(ex).__name__}: {ex}"
        if not hkl:
            return False, "GetKeyboardLayout returned 0"
        # The low word of an HKL is the LANGID, which is the LCID that
        # `locale.windows_locale` is keyed by — the same table
        # `_set_language_native` uses in the opposite direction.
        langid = hkl & 0xFFFF
        culture = locale.windows_locale.get(langid)
        if not culture:
            return False, f"no culture for LANGID 0x{langid:04x}"
        self.log.debug("Foreground layout: HKL=0x%x LANGID=0x%04x -> %s",
                       hkl, langid, culture)
        return True, culture.replace("_", "-")

    def _current_language_powershell(self):
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
        """Experimental: switch input language via Win32 LoadKeyboardLayout + PostMessage.

        ⚠️ **Every failure here falls through to `InputHelper.set_language`**,
        which is where the compatible-layout fallback lives. That matters most
        for the first one: a fold language has no LCID *by construction* —
        `locale.windows_locale` lists Windows cultures, and Tahitian, Filipino
        and Quechua are not among them — so returning False there made this
        setting silently switch off folds for the ~60 layouts that need them
        most. The no-foreground-window branch below always worked this way;
        the other two did not."""
        iso639 = f"{lang}-{country}"

        # Find LCID from Python's locale table (maps int LCID -> "lang_COUNTRY")
        target = f"{lang}_{country}".lower()
        lcid = next(
            (lcid_val for lcid_val, loc in locale.windows_locale.items()
             if loc.lower() == target),
            None,
        )
        if lcid is None:
            self.log.debug("Native set_language: no LCID for %s, falling back "
                           "to cycling + the compatibility map", iso639)
            return super().set_language(lang, country)

        klid = f"{lcid:08x}"
        user32 = ctypes.windll.user32
        hkl = user32.LoadKeyboardLayoutW(klid, _KLF_ACTIVATE)
        if not hkl:
            self.log.warning("Native set_language: LoadKeyboardLayout failed for "
                             "KLID %s (%s), falling back to cycling", klid, iso639)
            return super().set_language(lang, country)

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
