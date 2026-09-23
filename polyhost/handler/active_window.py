import logging
import os
import platform
import re
import subprocess
from urllib.parse import urlsplit

from polyhost.handler.common import (
    OverlayCommand, Flags, find_matching_entry, OS,
    TITLE, TITLE_SW, TITLE_EW, TITLE_HAS, URL, URL_HAS, FLAGS,
)
from polyhost.handler.remote_window import RemoteHandler
from polyhost.handler.own_process import (
    own_app_name, own_front_app, window_pid,
)
from polyhost.handler.win_process import app_name_for

IS_PLASMA = os.getenv("XDG_CURRENT_DESKTOP") == "KDE"
_IS_WAYLAND = os.getenv("XDG_SESSION_TYPE") == "wayland"

if IS_PLASMA:
    _BACKEND_NAME = "kde_win_reporter"
    import polyhost.handler.kde_win_reporter as pwc
elif _IS_WAYLAND:
    _BACKEND_NAME = "gnome_wayland_reporter"
    # pywinctl can't see native Wayland windows; use the GNOME Shell extension
    # reporter (untested — needs the 'Window Calls' extension). X11 is unaffected.
    import polyhost.handler.gnome_wayland_reporter as pwc
else:
    _BACKEND_NAME = "pywinctl"
    import pywinctl as pwc


#: AppleScript is the LIVE answer on any thread. `System Events` is asked fresh
#: every time, which is the whole reason it is used here instead of the AppKit
#: property one line of Python away -- see `frontmost_app`. The `try` with no
#: handler is AppleScript's, and mirrors pywinctl's own query: anything it cannot
#: resolve leaves the two values at their defaults and the caller sees an empty
#: name rather than an error.
_FRONTMOST_SCRIPT = """on run
    set procName to ""
    set procID to 0
    try
        tell application "System Events"
            set proc to first application process whose frontmost is true
            set procName to name of proc
            set procID to unix id of proc
        end tell
    end try
    return (procID as text) & linefeed & procName
end run"""

#: Bounds the one blocking call this module adds. The tick is ~600 ms and
#: `pywinctl` already spawns two or three `osascript` processes per poll with NO
#: timeout at all, so this is stricter than the code beside it, not looser.
_FRONTMOST_TIMEOUT_S = 2.0


def frontmost_app():
    """``(name, pid)`` for the focused application, or ``(None, None)``.

    The window backend's fall-back, for the case where it answers NOTHING.
    ``pywinctl.getActiveWindow()`` returns None for some macOS applications --
    it asks `System Events` for the frontmost process, then for that window's
    `AXTitle`, then matches the pid against `NSWorkspace.runningApplications()`,
    and a failure in either of the last two yields None. The overlay path does
    not need the window: it needs the app's NAME (to pick a template or draw a
    generic set) and its PID (for the OS icon and the AX shortcut harvest).

    ⚠️ **NOT `NSWorkspace.frontmostApplication`, which is STALE off the main
    thread -- this is the second time that property has been trusted in this
    codebase and the second time it was wrong.** The first was the shortcut
    fetcher, where nine consecutive harvests over three minutes all read
    `Safari`, so exactly one app could ever harvest. Here it froze on
    `QuickTime Player`: switching to Activity Monitor drew QuickTime's icon and
    logged nothing at all, because the name never changed (field, 2026-09-22).
    It is a KVO property published through the main run loop, and the window
    tick runs on the core's own thread -- in the headless daemon there is no
    NSApplication run loop to publish it at all.

    A wrong app is worse than no app: the board confidently draws another
    program's mark and shortcuts, which reads as the feature working.

    ⚠️ macOS only; ``(None, None)`` everywhere else. The Windows and Linux
    backends do not have this failure mode, and a second opinion about which app
    is focused is a way for two answers to disagree.

    ⚠️ It never raises. A fall-back that can kill the poll is worse than no
    fall-back.
    """
    try:
        if platform.system() != "Darwin":
            return None, None
        out = subprocess.run(
            ["osascript", "-"], input=_FRONTMOST_SCRIPT, text=True,
            capture_output=True, timeout=_FRONTMOST_TIMEOUT_S).stdout
        # `procID` first because a process NAME may contain anything, including
        # whitespace; the pid is digits and ends at the first newline.
        pid, _, name = (out or "").strip().partition("\n")
        name = name.strip()
        if not name:
            return None, None
        try:
            # 0 is the script's own "not resolved" default, and is never a real
            # application pid. A name without a usable pid still picks the
            # template and drives the lexicon; only the OS icon and the AX
            # harvest need the pid, and both already handle None.
            return name, (int(pid) or None)
        except ValueError:
            return name, None
    except Exception:  # noqa: BLE001 - a fall-back must never raise
        return None, None


def _handle_identifies(handle):
    """True when ``handle`` names a particular window.

    ⚠️ On macOS it often does NOT, and that is not a corner case.
    pywinctl derives the handle FROM the title -- ``MacOSWindow.getHandle()``
    returns ``("", "")`` whenever ``title`` is empty, and ``title`` is empty for
    every window ``System Events`` reports no ``AXTitle`` for. So two *different*
    untitled applications are byte-identical to the change test below, the switch
    between them is never noticed, and the previous app's overlays stay on the
    keycaps with nothing logged (field, 2026-09-21: VS Code, Maps and Chess in a
    row, none of which appeared in the log at all).

    Windows and the Linux reporters hand back an integer id that is never empty,
    so they take the first branch and are unaffected.
    """
    if handle is None:
        return False
    if isinstance(handle, tuple):
        return any(handle)
    return True


def log_env_info(log):
    """Log OS, desktop environment, session type, display vars, and the selected
    active-window backend. Call once at startup from any entry point that does
    window tracking (OverlayHandler on the keyboard machine, PolyForwarder on
    remote machines)."""
    log.info(
        "Platform: %s %s | Desktop: %s | Session: %s | "
        "DISPLAY: %s | WAYLAND_DISPLAY: %s | Window backend: %s",
        platform.system(), platform.release(),
        os.getenv("XDG_CURRENT_DESKTOP", "n/a"),
        os.getenv("XDG_SESSION_TYPE", "n/a"),
        os.getenv("DISPLAY", "n/a"),
        os.getenv("WAYLAND_DISPLAY", "n/a"),
        _BACKEND_NAME,
    )


# TITLE/TITLE_SW/TITLE_EW/TITLE_HAS/FLAGS are imported from common (shared with
# the matcher and RemoteHandler).
INDEX = "index"
OVERLAY = "overlay"
REMOTE = "remote"


class OverlayHandler:
    """Reads the overlay mapping file and provides information which overlay
    should be displayed depending on the program context."""

    def __init__(self, mapping, url_provider=None, enable_legacy_relay=False,
                 rpc_relay_enabled=False):
        self.log = logging.getLogger("PolyHost")
        log_env_info(self.log)
        self.last_update_msec = 0
        self.prev_win = None
        self.win = None
        self.title = None
        self.handle = None
        # url_provider(app_name) -> Optional[str]: the URL of the focused window
        # when it is a browser reporting its active tab, else None. Injected by
        # PolyCore (BrowserUrlProvider.current_url); None disables URL matching
        # (behaviour identical to before this feature). current_url holds the
        # value used for the most recent match, for logging.
        self.url_provider = url_provider
        self.current_url = None
        self.current_entry = None
        # The focused app's NORMALISED name, as the matcher saw it. Kept so the
        # generic-icon path can ask about the same application the mapping was
        # tested against -- re-deriving it there would be a second normaliser
        # free to disagree with this one.
        self.app_name = None
        # The same two facts for an application the window backend cannot see at
        # all -- name and pid straight from the OS, no window and so no title.
        # See the no-window branch of `_decide_active_window`.
        self.windowless_app = None
        self.windowless_pid = None
        self.last_entry = None
        # Tracks whether overlays are currently enabled on the device, so a
        # same-app title change doesn't re-issue an ENABLE that's already in
        # effect (see handle_active_window).
        self.overlays_enabled = False
        self.mapping = self.annotate(mapping.items())
        self.remote_handler = RemoteHandler(
            self.mapping, enable_legacy_relay=enable_legacy_relay,
            rpc_relay_enabled=rpc_relay_enabled)

    def annotate(self, entries, return_copy=True):
        """Annotate the provided mapping (from yaml) so that it can
        be used faster when looking for the program overlay.

        Args:
            entries (dict_items): The deserialized yaml
            return_copy (bool, optional): Used internally, do not set

        Returns:
            dict: An annotated dict to be used for program to overlay mapping
        """
        result = {}
        for keys, entry in entries:
            has_overlay = OVERLAY in entry.keys()
            has_remote = REMOTE in entry.keys()
            has_title = TITLE in entry.keys()
            has_starts_with = TITLE_SW in entry.keys() and entry[TITLE_SW]
            has_ends_with = TITLE_EW in entry.keys() and entry[TITLE_EW]
            has_contains = TITLE_HAS in entry.keys() and entry[TITLE_HAS]
            has_url = URL in entry.keys()
            has_urls_contains = URL_HAS in entry.keys() and entry[URL_HAS]
            has_os = OS in entry.keys() and entry[OS]

            entry[FLAGS] = [
                has_overlay,
                has_remote,
                has_title,
                has_starts_with,
                has_ends_with,
                has_contains,
                has_url,
                has_urls_contains,
                has_os,
            ]
            if has_starts_with:
                self.annotate(entry[TITLE_SW].items(), False)
            if has_ends_with:
                self.annotate(entry[TITLE_EW].items(), False)
            if has_contains:
                self.annotate(entry[TITLE_HAS].items(), False)
            if has_urls_contains:
                self.annotate(entry[URL_HAS].items(), False)
            if has_os:
                self.annotate(entry[OS].items(), False)

            if return_copy:
                keys = keys.split(",")
                for key in keys:
                    result[key.strip().lower()] = entry

        return result

    def set_win(self, win=None, title=None, handle=None):
        """Set the active window.

        ⚠️ **Clears `app_name` too, and that is the point of it.** `set_win()`
        with no arguments means "there is no focused window", and until
        2026-09-21 it left `app_name` holding the LAST app -- so `focused_app()`
        went on naming an application that was no longer in front of the user,
        and `PolyCore._maybe_send_generic_overlays` kept re-affirming that app's
        icons. The window path is re-derived a few lines below on every genuine
        change, so nothing that needs the name loses it.

        Same class of bug as the stale `NSWorkspace.frontmostApplication` on a
        worker thread: a value that is right until focus moves and then silently
        wrong, with nothing saying so.
        """
        self.win = win
        self.title = title
        self.handle = handle
        self.app_name = None
        # The window path and the windowless one are alternatives, never both:
        # whichever ran last is the answer, so entering one clears the other.
        self.windowless_app = None
        self.windowless_pid = None

    def _active_os(self):
        """OS of the machine running the focused app, for the mapping's `os` branch.

        Mirrors PolyCore._track_active_os: a forwarded window's shortcuts belong to
        the FORWARDER's platform, not to whichever machine the keyboard is plugged
        into — so a Mac forwarding to a Windows host must still get Mac artwork.
        Falls back to the local OS when nothing is forwarded (or the forwarder
        reported UNKNOWN/none)."""
        rh = getattr(self, "remote_handler", None)
        if rh is not None and self.is_remote_mapping_entry():
            forwarded = getattr(rh, "forwarded_os", None)
            if forwarded:
                return forwarded
        try:
            from polyhost.input.unicode_input import get_host_os
            return get_host_os()
        except Exception:            # never let OS detection break window matching
            return None

    def try_to_match_window(self, name, entry):
        # The recursion lives in common.find_matching_entry (shared with the
        # remote path); here we add the ENABLE-vs-OFF_ON decision and the
        # current/last-entry bookkeeping. A re-enter of the same matched entry
        # is ENABLE (overlays already mapped); a different one is a full OFF_ON.
        try:
            matched = find_matching_entry(self.title, entry, self.current_url,
                                          self._active_os())
        except re.error as e:
            self.log.warning(
                "Cannot match entry '%s': %s, because '%s'@%d with '%s'",
                name, entry, e.msg, e.pos, e.pattern,
            )
            return False, OverlayCommand.NONE

        if matched is None:
            return False, OverlayCommand.NONE
        if self.last_entry == matched:
            self.current_entry = matched
            return True, OverlayCommand.ENABLE
        self.current_entry = matched
        self.last_entry = matched
        return True, OverlayCommand.OFF_ON

    def log_win(self, raw_app_name):
        """Log active window.

        ⚠️ The handle is formatted with **%s, never %d**. It is an opaque token
        whose type is the platform's: an int HWND on Windows, an int id on the
        Linux reporters — and on macOS a **tuple**, which is what pywinctl's
        `MacOSWindow.getHandle()` returns. ⚠️ Measured on Darwin 22.6.0, its
        members are `(app name, window title)` — e.g.
        `('Google Chrome', 'Claude Code - Google Chrome')` — NOT a numeric
        window id, so it is not a stable identity either: it changes whenever
        the title does. Harmless, because the only test applied to it is
        equality and `local_win_changed` compares the title anyway. `%d` on it
        raises `TypeError: %d format: a real number is required, not tuple`,
        and this line sits inside the `try` whose `except` logs "Failed
        retrieving active window", so the whole app reported **no active window
        at all, forever, on every Mac** — no overlays and no per-app language
        switch — over a cosmetic log line (field, 2026-09-21). Nothing compares
        or arithmetics the handle; it is only ever tested for equality, so
        there is no reason to demand a number of it.
        """
        self.log.info("Active App Changed: \"%s\", Title: \"%s\"  Handle: %s",
                      raw_app_name, self.win.title.encode('utf-8'),
                      self.win.getHandle())

    def _is_redundant_overlay_cmd(self, cmd):
        """True when ``cmd`` asks for the overlay state the device is already in
        (ENABLE while on, or DISABLE while off) — a no-op the caller should drop
        rather than pay a blocking slave bridge-sync + full 72-keycap refresh for
        no visible change. The DISABLE side fires every poll for an unmapped
        window whose *title* keeps ticking (e.g. a terminal CLI animating a
        spinner in its title bar); the ENABLE side for a same-app title change."""
        return ((cmd == OverlayCommand.ENABLE and self.overlays_enabled)
                or (cmd == OverlayCommand.DISABLE and not self.overlays_enabled))

    def note_overlay_state(self, enabled):
        """Set the tracked device overlay state. PolyCore calls this after it
        runs the enable/disable on the device so that a FAILED command re-arms
        the redundant-command guard — reverting to the pre-command state so the
        next poll retries instead of ``_is_redundant_overlay_cmd`` swallowing it
        (a failed DISABLE must not leave overlays showing with the host believing
        they are off, and vice-versa)."""
        self.overlays_enabled = enabled

    def handle_active_window(self, update_cycle_time_msec, accept_time_msec):
        """Decide the overlay action for the focused window and track the
        resulting device overlay state, suppressing a redundant re-ENABLE or
        re-DISABLE (see ``_is_redundant_overlay_cmd``). Only a genuine
        transition is forwarded; the state is advanced optimistically here and
        re-armed by ``PolyCore._overlay_cmd_job`` (``note_overlay_state``) if the
        device call fails, so a failed command is retried rather than dropped."""
        data, cmd = self._decide_active_window(update_cycle_time_msec, accept_time_msec)
        if self._is_redundant_overlay_cmd(cmd):
            return None, OverlayCommand.NONE
        if cmd in (OverlayCommand.ENABLE, OverlayCommand.OFF_ON):
            self.overlays_enabled = True
        elif cmd == OverlayCommand.DISABLE:
            self.overlays_enabled = False
        return data, cmd

    def _decide_active_window(self, update_cycle_time_msec, accept_time_msec):
        self.last_update_msec = self.last_update_msec + update_cycle_time_msec
        win = None
        # macOS only, None elsewhere: our own window, which pywinctl cannot
        # see there (see `own_process.own_front_app`). It takes the
        # windowless path below, named `polyhost`.
        own = own_front_app()
        if own is None:
            try:
                win = pwc.getActiveWindow()
            except Exception as e:
                self.log.warning("Failed retrieving active window: %s", e)

        if win:
            if self.prev_win != win:
                self.prev_win = win
                self.last_update_msec = 0
            if self.last_update_msec > accept_time_msec:
                self.last_update_msec = accept_time_msec  * 2 #just to limit that
                # ⚠️ Read each of these ONCE. On macOS every access is an
                # `osascript` subprocess -- `MacOSWindow.title` re-runs
                # `_getAppWindowsTitles` and `getHandle()` calls `title` again --
                # so the old four accesses per changed tick cost four AppleScript
                # round trips where two do.
                handle = win.getHandle()
                title = win.title
                if not title and not _handle_identifies(handle):
                    # The window identifies nothing, so fall back to the app the
                    # window belongs to (see `_handle_identifies`). On macOS
                    # `getAppName()` is a cached attribute read, not another
                    # AppleScript call.
                    handle = win.getAppName()
                local_win_changed = (
                    self.win is None
                    or handle != self.handle
                    or title != self.title
                )

                if local_win_changed:
                    # remember active window
                    self.set_win(win, title, handle)
                    if title == "PolyHost":
                        return None, OverlayCommand.NONE
                    try:
                        raw_app_name = app_name_for(self.win)
                        self.log_win(raw_app_name)
                        if self.mapping:
                            found = False
                            if platform.system() == 'Windows':
                                app_name = raw_app_name.split(".",-1)[0].lower()
                            else:
                                app_name = raw_app_name.lower()
                            # PolyHost's own windows report the interpreter
                            # (`pythonw`, `python3`); name them as ours so the
                            # ESC mark is the PolyKybd logo, not Python's.
                            app_name = own_app_name(app_name, self._win_pid())
                            self.app_name = app_name
                            # For a browser, resolve the focused tab's URL so the
                            # matcher can key overlays off the website (see
                            # handler/browser_url.py). None for non-browsers or
                            # when no reporter is available — matching then falls
                            # back to app-name + title exactly as before.
                            self.current_url = (
                                self.url_provider(app_name) if self.url_provider else None
                            )
                            if self.current_url:
                                # Log only the origin (scheme+host): the full URL
                                # can carry PII in the path/query (account ids,
                                # ticket numbers). Matching still uses the full
                                # self.current_url.
                                origin = urlsplit(self.current_url)
                                self.log.debug_detailed(
                                    "Browser URL for %s: %s://%s", app_name,
                                    origin.scheme, origin.netloc)
                            # self.log.debug("App lookup: raw='%s' normalized='%s' in_mapping=%s", raw_app_name, app_name, app_name in self.mapping)
                            if app_name in self.mapping.keys():
                                found, cmd = self.try_to_match_window(
                                    app_name, self.mapping[app_name]
                                )
                                if found:
                                    self.log.info("Changing to %s", app_name)
                                    return self.get_overlay_data(), cmd
                                self.log.debug("App '%s' in mapping but title did not match (title='%s')", app_name, self.title)
                            if self.current_entry and not found:
                                self.current_entry = None
                                self.log.info("Nothing active")
                                return None, OverlayCommand.DISABLE
                    except Exception as e:
                        self.log.warning("Failed retrieving active window: %s", e)
                    self.log.info("No match")
                    return None, OverlayCommand.DISABLE
                elif self.is_remote_mapping_entry():
                    self.log.debug_detailed("Remote forwarder active (current_entry='%s'), checking for changes", self.current_entry.get("remote") if self.current_entry else None)
                    if self.remote_handler.remote_changed(self.current_entry):
                        self.log.info("Remote window changed")
                        if self.remote_handler.has_overlay():
                            return self.get_overlay_data(), OverlayCommand.OFF_ON
                        else:
                            return None, OverlayCommand.DISABLE
        else:
            # ⚠️ NO WINDOW IS NOT NO APPLICATION, and treating the two as the
            # same left three apps with a blank board. `getActiveWindow()`
            # returns None for some macOS apps -- Photos, Notes and Freeform,
            # measured, while Chess and Maps on the same desktop answered fine
            # -- and the overlay path never needed the window itself: it needs
            # the app's name and pid, which `frontmost_app()` knows.
            #
            # What is lost without a window is the TITLE, so a template entry
            # that matches on one cannot be evaluated. That is why this still
            # returns DISABLE and leaves `current_entry` cleared: the generic
            # path draws (`focused_app`/`focused_pid` answer from here), the
            # template path correctly does not.
            name, pid = own if own is not None else frontmost_app()
            app = own_app_name(name.lower(), pid) if name else None
            if self.win is not None or app != self.windowless_app:
                self.set_win()
                self.windowless_app, self.windowless_pid = app, pid
                if own is not None:
                    self.log.info("Active App Changed: PolyHost's own window "
                                  "(pid %s)", pid)
                elif app:
                    self.log.info(
                        "No active window: the window backend (%s) reports none "
                        "while '%s' is frontmost -- drawing it from the app "
                        "name, without a title", _BACKEND_NAME, name)
                else:
                    self.log.info("No active window")
                # ⚠️ DISABLE whether or not a TEMPLATE was active. The guard
                # used to be `if self.current_entry`, which asks "was a
                # hand-made overlay set on the board?" -- a question that was
                # the whole story before the generic path existed and is half
                # of it now. A generically-drawn app has no `current_entry`, so
                # losing the window left its mark and its 48 shortcut icons on
                # the keycaps, describing an application the user had already
                # left (field, 2026-09-21: switching to an app the window
                # handler cannot see kept the previous app's mark on ESC).
                #
                # Safe to send unconditionally: `_is_redundant_overlay_cmd`
                # drops a DISABLE while the device already has overlays off, so
                # this costs a bridge-sync only when something really is drawn.
                self.current_entry = None
                return None, OverlayCommand.DISABLE

        # self.log.info("Nothing at all")
        return None, OverlayCommand.NONE

    def focused_app(self):
        """``(name, identity)`` for the focused application, or ``(None, None)``.

        ``identity`` is an :class:`AppIdentity` only for a FORWARDED window, where
        the forwarder already resolved it on the machine running the app. It is
        None for a local window, which this machine resolves itself.

        ⚠️ Both come from here rather than from the caller re-deriving them: the
        name is the one the MATCHER used, so "no template covers this app" and
        "draw a generic mark for this app" can never disagree about which
        application they mean.
        """
        rh = getattr(self, "remote_handler", None)
        if rh is not None and self.is_remote_mapping_entry():
            name = getattr(rh, "name", None)
            if name:
                return name, rh.forwarded_identity(name)
            return None, None
        # ⚠️ `windowless_app` is the SAME question answered without a window
        # (see the no-window branch of `_decide_active_window`). It must be
        # consulted here rather than at the caller, so "which app is focused"
        # has one answer -- the mark and the shortcut harvest would otherwise be
        # able to disagree about it.
        return self.app_name or self.windowless_app, None

    def focused_pid(self):
        """The focused LOCAL window's process id, or None.

        ⚠️ The OS-icon route needs this and NOTHING WAS PASSING IT, so the whole
        route was dead on the local path -- on every platform, not just macOS.
        `app_icon_fetcher.overlay_for()` takes a `pid`, `os_app_icon.app_identity()`
        takes it as given and resolves none of its own, and the only production
        caller (`PolyCore._maybe_send_generic_overlays`) passed neither it nor an
        identity for a local window. So `_macos_identity` got None, `int(None)`
        raised inside `_macos_bundle`, and every app logged
        `(OS names: <none>)` -- the aggregate line that cannot say why (field,
        2026-09-21). The `pid` parameter and its tests existed the whole time;
        production simply never used them.

        ⚠️ **None for a FORWARDED window, deliberately.** That app runs on the
        other machine, so a local pid names an unrelated process -- and the
        identity that travels with the report is the right answer there, which
        `focused_app` already returns.

        `getPID()` is on pywinctl's abstract Window and implemented by all three
        backends, so this is not a macOS special case. It is still guarded: a
        cosmetic lookup must not take the overlay send with it.
        """
        rh = getattr(self, "remote_handler", None)
        if rh is not None and self.is_remote_mapping_entry():
            return None
        if self.win:
            return self._win_pid()
        # No window, but possibly still an app -- and the pid is what makes the
        # OS icon and the macOS AX harvest reachable, so losing it here would
        # leave a windowless app with a name and nothing to draw.
        return self.windowless_pid

    def _win_pid(self):
        """The focused local window's pid, or None if it cannot be read."""
        return window_pid(self.win) if self.win else None

    def is_remote_mapping_entry(self):
        return (
            self.current_entry
            and self.current_entry[FLAGS][Flags.HAS_REMOTE.value]
        )  # 0 for remote

    def get_overlay_data(self):
        if (
            self.current_entry
            and self.current_entry[FLAGS][Flags.HAS_OVERLAY.value]
        ):  # 0 for overlay
            return self.current_entry[OVERLAY]
        elif self.remote_handler.has_overlay():
            return self.remote_handler.get_overlay_data()
        return None

    def covered_by_template(self) -> bool:
        """Does a hand-made overlay set cover the focused window RIGHT NOW?

        ⚠️ Not "did one just get sent". `handle_active_window` returns the
        template filenames only on the tick the window CHANGES; every tick after
        that it answers `(None, NONE)` for the same window. So a caller that
        reads "a template is active" off the returned data sees it once and then
        believes there is none -- which is how the generic fall-back came to
        overwrite the template one tick after it landed, blanking every keycap
        the hand-made set had just drawn (field, 2026-09-18).

        Answered from `get_overlay_data()` rather than from `current_entry`
        alone, so it cannot disagree with what a send would actually carry: a
        matched entry with no overlay flag, and a remote entry whose forwarder
        has no overlay, are both "not covered".
        """
        return self.get_overlay_data() is not None

    def invalidate_window_cache(self):
        """Force the next poll to re-evaluate the focused window even if the OS
        reports no window/title change.

        A browser SPA can navigate to a new site (a new URL) without changing its
        window title, so the pywinctl-driven change detection would miss it. When
        a fresh browser URL report arrives for the active browser, PolyCore calls
        this so the next ``handle_active_window`` re-matches with the new URL and
        swaps overlays. Cheap: just drops the cached title so ``local_win_changed``
        trips next tick — the accept-time debounce is untouched (the window has
        already been focused, so the re-match fires promptly)."""
        self.title = None
        self.handle = None

    def force_resend(self):
        """Reset window tracking so the next cycle triggers a fresh OFF_ON resend."""
        self.win = None
        self.title = None
        self.handle = None
        self.last_entry = None
        self.last_update_msec = 0
        # The device's overlays were reset/cleared on (re)connect, so the next
        # match must be allowed to enable them again (don't suppress).
        self.overlays_enabled = False
        self.remote_handler.reset_for_resend()

    def close(self):
        self.remote_handler.close()
