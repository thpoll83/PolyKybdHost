"""Shared file-dialog helpers that pick the best picker per platform.

Qt's ``QFileDialog`` static helpers use the OS-native picker by default, but
on Linux "native" is not one dialog — it is whatever the Qt platform-theme
plugin provides, and its quality varies by desktop:

- **Windows / macOS** — native, the expected platform look.
- **Linux KDE / Plasma** — native, which (with ``plasma-integration``) is the
  modern KFileWidget / xdg-desktop-portal dialog: places panel, previews, and
  it respects the user's KDE settings. Much nicer than Qt's built-in dialog.
  If ``plasma-integration`` is absent Qt falls back to its own widget dialog
  anyway, so requesting native here is safe.
- **Other Linux (GNOME, …)** — NOT native: there "native" is the GTK dialog,
  which looks foreign in this PyQt5 app. Use Qt's own widget dialog instead
  for a consistent look.

Route every open/save picker through these wrappers instead of calling
``QFileDialog.getOpenFileName`` / ``getSaveFileName`` directly. They call the
same static methods (so unit tests that patch ``QFileDialog.getOpenFileName``
still work), only toggling the ``DontUseNativeDialog`` option per the policy
above.

``cmd_menu._get_open_file_explicit`` is a richer variant that always forces the
Qt dialog (and defeats KDE's single-click-to-accept); it predates this module.
"""
import os
import sys

from PyQt5.QtWidgets import QFileDialog


def _is_kde():
    """True on a KDE/Plasma session (matches the window-reporter backend check)."""
    for var in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP"):
        if "kde" in os.environ.get(var, "").lower():
            return True
    return bool(os.environ.get("KDE_FULL_SESSION"))


def _use_native():
    """Whether to let Qt use the OS-native dialog (see module docstring)."""
    if sys.platform in ('win32', 'darwin'):
        return True
    return _is_kde()


def _dialog_options():
    """No native flag when native is wanted; DontUseNativeDialog otherwise."""
    if _use_native():
        return QFileDialog.Options()
    return QFileDialog.DontUseNativeDialog


def get_open_file_name(parent, caption, directory="", name_filter=""):
    """Drop-in for ``QFileDialog.getOpenFileName`` that uses the native dialog on
    Windows/macOS/KDE and the Qt dialog elsewhere. Returns the
    ``(path, selected_filter)`` tuple, same as Qt."""
    return QFileDialog.getOpenFileName(
        parent, caption, directory, name_filter, options=_dialog_options())


def get_save_file_name(parent, caption, directory="", name_filter=""):
    """Drop-in for ``QFileDialog.getSaveFileName`` that uses the native dialog on
    Windows/macOS/KDE and the Qt dialog elsewhere. Returns the
    ``(path, selected_filter)`` tuple, same as Qt."""
    return QFileDialog.getSaveFileName(
        parent, caption, directory, name_filter, options=_dialog_options())
