import logging
import os
import platform
import re

from polyhost.handler.common import (
    OverlayCommand, Flags, find_matching_entry,
    TITLE, TITLE_SW, TITLE_EW, TITLE_HAS, FLAGS,
)
from polyhost.handler.remote_window import RemoteHandler

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

    def __init__(self, mapping, enable_legacy_relay=False, rpc_relay_enabled=False):
        self.log = logging.getLogger("PolyHost")
        log_env_info(self.log)
        self.last_update_msec = 0
        self.prev_win = None
        self.win = None
        self.title = None
        self.handle = None
        self.current_entry = None
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

            entry[FLAGS] = [
                has_overlay,
                has_remote,
                has_title,
                has_starts_with,
                has_ends_with,
                has_contains,
            ]
            if has_starts_with:
                self.annotate(entry[TITLE_SW].items(), False)
            if has_ends_with:
                self.annotate(entry[TITLE_EW].items(), False)
            if has_contains:
                self.annotate(entry[TITLE_HAS].items(), False)

            if return_copy:
                keys = keys.split(",")
                for key in keys:
                    result[key.strip().lower()] = entry

        return result

    def set_win(self, win=None, title=None, handle=None):
        """Set the active window"""
        self.win = win
        self.title = title
        self.handle = handle

    def try_to_match_window(self, name, entry):
        # The recursion lives in common.find_matching_entry (shared with the
        # remote path); here we add the ENABLE-vs-OFF_ON decision and the
        # current/last-entry bookkeeping. A re-enter of the same matched entry
        # is ENABLE (overlays already mapped); a different one is a full OFF_ON.
        try:
            matched = find_matching_entry(self.title, entry)
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
        """Log active window"""
        self.log.info("Active App Changed: \"%s\", Title: \"%s\"  Handle: %d", raw_app_name, self.win.title.encode('utf-8'), self.win.getHandle())

    def handle_active_window(self, update_cycle_time_msec, accept_time_msec):
        """Decide the overlay action for the focused window and track the
        resulting device state, suppressing redundant re-enables.

        When the same app stays focused and only the window *title* changes,
        the matcher returns ENABLE, but overlays are already on and nothing was
        resent — re-enabling just costs a blocking slave bridge-sync + full
        keycap refresh on the keyboard for no visible change. We downgrade that
        to NONE. A genuine re-enable (overlays were turned off since, e.g. after
        an unmapped window) still goes through because overlays_enabled is then
        False."""
        data, cmd = self._decide_active_window(update_cycle_time_msec, accept_time_msec)
        if cmd == OverlayCommand.ENABLE and self.overlays_enabled:
            return None, OverlayCommand.NONE
        if cmd in (OverlayCommand.ENABLE, OverlayCommand.OFF_ON):
            self.overlays_enabled = True
        elif cmd == OverlayCommand.DISABLE:
            self.overlays_enabled = False
        return data, cmd

    def _decide_active_window(self, update_cycle_time_msec, accept_time_msec):
        self.last_update_msec = self.last_update_msec + update_cycle_time_msec
        win = None
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
                local_win_changed = (
                    self.win is None
                    or win.getHandle() != self.handle
                    or win.title != self.title
                )

                if local_win_changed:
                    # remember active window
                    self.set_win(win, win.title, win.getHandle())
                    if win.title == "PolyHost":
                        return None, OverlayCommand.NONE
                    try:
                        raw_app_name = self.win.getAppName()
                        self.log_win(raw_app_name)
                        if self.mapping:
                            found = False
                            if platform.system() == 'Windows':
                                app_name = raw_app_name.split(".",-1)[0].lower()
                            else:
                                app_name = raw_app_name.lower()
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
            if self.win:
                self.log.info("No active window")
                self.set_win()
                if self.current_entry:
                    self.current_entry = None
                    return None, OverlayCommand.DISABLE

        # self.log.info("Nothing at all")
        return None, OverlayCommand.NONE

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
