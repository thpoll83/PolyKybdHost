"""Integrations -> GNOME: install the PolyKybd Window Reporter extension
(services/gnome_extension.py). The dialog shows this page only on GNOME."""
from __future__ import annotations

from polyhost.gui.integrations_dialog import RowsPage
from polyhost.i18n import _, _f
from polyhost.services import gnome_extension

EXTENSION = "extension"
USER_EXTENSIONS = "user-extensions"


def extension_state_text(st):
    """The extension row's state, translated."""
    if st.files == "missing":
        return _("Not installed")
    if st.files == "other":
        return _("Another version is installed. Install replaces it with the version "
                 "this app uses.")
    if st.enabled is False:
        return _("Installed, but not enabled")
    if st.active:
        return _("Installed and active")
    if st.user_off:
        return _("Installed, but GNOME loads no user extension (see below)")
    if st.active is False:
        return _("Installed. GNOME starts it at the next login.")
    return _("Installed")


def result_line(r):
    """One install/remove result, translated."""
    m = gnome_extension
    return {
        m.MSG_INSTALLED: lambda: _f("Window Reporter: installed in {path}", path=r.detail),
        m.MSG_UPDATED: lambda: _f("Window Reporter: replaced with the version this app "
                                  "uses ({path})", path=r.detail),
        m.MSG_UP_TO_DATE: lambda: _f("Window Reporter: already installed ({path})",
                                     path=r.detail),
        m.MSG_REMOVED: lambda: _("Window Reporter: removed"),
        m.MSG_NOT_INSTALLED: lambda: _("Window Reporter: was not installed"),
        m.MSG_USER_ON: lambda: _("User extensions: switched on"),
    }.get(r.message, lambda: _f("The change failed: {error}", error=r.detail))()


class GnomePage(RowsPage):
    """``status_fn``, ``install_fn`` and ``remove_fn`` are the service's
    functions; tests pass fakes."""

    APPLY_ON_THREAD = True

    def __init__(self, parent=None, status_fn=None, install_fn=None, remove_fn=None):
        super().__init__("GNOME", _(
            "On GNOME with Wayland, the keyboard shows the keys of the focused app only "
            "with the PolyKybd Window Reporter extension. Without it, only apps that run "
            "under XWayland are seen. The extension reports the focused window's name "
            "and title and cannot change any window.\n\n"
            "Install downloads a fixed version of the extension from "
            "github.com/thpoll83/gnome-wayland-winreader, checks it, copies it to "
            "GNOME's extensions folder and enables it. GNOME starts a new extension "
            "only at login, so log out and back in after installing."), parent)
        self._status_fn = status_fn or gnome_extension.status
        self._install_fn = install_fn or gnome_extension.install
        self._remove_fn = remove_fn or gnome_extension.remove
        self._status = None
        self.refresh()

    def status_error_text(self, exc):
        return _f("The extension could not be checked: {error}", error=str(exc))

    def read_status(self):
        return self._status_fn()

    def show_status(self, st):
        self._status = st
        old = {k: b.isChecked() for k, b in self.boxes().items()}
        self.clear_rows()
        done = st.files == "current" and st.enabled
        self.add_row(EXTENSION, "Window Reporter", str(st.folder), extension_state_text(st),
                     checked=old.get(EXTENSION, not done))
        info = []
        if st.user_off:
            if st.user_off_writable is False:
                state = _("Off, and locked by an administrator: GNOME loads no user "
                          "extension, so the Window Reporter cannot run.")
            else:
                state = _("Off: GNOME loads no user extension, so the Window Reporter "
                          "cannot run. Install with this row selected switches on every "
                          "user extension, not only this one.")
            # Opt-in: the setting affects every user extension, so it is never
            # ticked for the user. Remove does not switch it off again.
            self.add_row(USER_EXTENSIONS, _("User extensions"),
                         "org.gnome.shell disable-user-extensions", state,
                         checked=old.get(USER_EXTENSIONS, False),
                         enabled=st.user_off_writable is not False, removable=False)
        if st.error:
            info.append(_f("GNOME's settings could not be read: {error}", error=st.error))
        if not st.wayland:
            info.append(_("This is an X11 session: the keyboard sees every window without "
                          "the extension. It is needed in a Wayland session."))
        elif done and st.active is False and not st.user_off:
            info.append(_("Log out and back in to start the extension."))
        self.set_info("\n".join(info))

    def apply(self, install, keys):
        # Runs on the worker thread.
        if install:
            results = self._install_fn(extension=EXTENSION in keys,
                                       user_extensions=USER_EXTENSIONS in keys)
        else:
            results = self._remove_fn()
        lines = [result_line(r) for r in results]
        if install and any(r.changed for r in results):
            lines.append(_("Log out and back in: GNOME starts a new extension only at "
                           "login."))
        return lines
