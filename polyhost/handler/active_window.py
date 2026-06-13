import logging
import os
import platform
import re

from polyhost.handler.common import OverlayCommand, Flags
from polyhost.handler.remote_window import RemoteHandler

IS_PLASMA = os.getenv("XDG_CURRENT_DESKTOP") == "KDE"

if not IS_PLASMA:
    import pywinctl as pwc
else:
    import polyhost.handler.kde_win_reporter as pwc


TITLE_SW = "titles-startswith"
TITLE_EW = "titles-endswith"
TITLE_HAS = "titles-contains"
TITLE = "title"
INDEX = "index"
FLAGS = "flags"
OVERLAY = "overlay"
REMOTE = "remote"


class OverlayHandler:
    """Reads the overlay mapping file and provides information which overlay
    should be displayed depending on the program context."""

    def __init__(self, mapping):
        self.log = logging.getLogger("PolyHost")
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
        self.remote_handler = RemoteHandler(self.mapping)

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
        (
            has_overlay,
            has_remote,
            has_title,
            has_starts_with,
            has_ends_with,
            has_contains,
        ) = entry[FLAGS]
        match = has_overlay or has_remote
        try:
            if match:
                words = self.title.split() if (self.title and (has_starts_with or has_ends_with)) else []
                if len(words) > 0:
                    if (
                        has_starts_with
                        and words[0] in entry[TITLE_SW].keys()
                    ):
                        found, cmd = self.try_to_match_window(
                            name, entry[TITLE_SW][words[0]]
                        )
                        if found:
                            return True, cmd
                    if (
                        has_ends_with
                        and words[-1] in entry[TITLE_EW].keys()
                    ):
                        found, cmd = self.try_to_match_window(
                            name, entry[TITLE_EW][words[-1]]
                        )
                        if found:
                            return True, cmd
                    if has_contains:
                        contains = entry[TITLE_HAS]
                        for word in words:
                            if word in contains.keys():
                                found, cmd = self.try_to_match_window(name, contains[word])
                                if found:
                                    return True, cmd
                if self.title and has_title:
                    match = match and re.search(entry[TITLE], self.title)
        except re.error as e:
            self.log.warning(
                "Cannot match entry '%s': %s, because '%s'@%d with '%s'",
                name,
                entry,
                e.msg,
                e.pos,
                e.pattern,
            )
            return False, OverlayCommand.NONE

        if match:
            if self.last_entry == entry:
                self.current_entry = entry
                return True, OverlayCommand.ENABLE
            self.current_entry = entry
            self.last_entry = entry
            return True, OverlayCommand.OFF_ON
        return False, OverlayCommand.NONE

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
