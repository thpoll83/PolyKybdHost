"""Shared file-dialog helpers that pick the best picker per platform.

Qt's ``QFileDialog`` static helpers use the OS-native picker by default, but
on Linux "native" is not one dialog — it is whatever the Qt platform-theme
plugin provides, and its quality varies by desktop:

- **Windows / macOS** — native, the expected platform look.
- **Linux KDE / Plasma** — native, so the file picker is the modern Plasma
  dialog (places panel, previews, respects KDE settings). ⚠️ We run a **pip /
  venv PyQt5**, whose bundled Qt ships **no** KDE ``plasma-integration`` plugin,
  so a plain "native" dialog would fall back to Qt's old widget dialog even on
  KDE. The bundled Qt *does* ship the **xdg-desktop-portal** plugin, and KDE
  runs ``xdg-desktop-portal-kde``, so ``maybe_set_portal_platformtheme()``
  (called once at GUI startup) points Qt at that theme — which is what actually
  produces the Plasma picker here.
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


def use_native():
    """Whether to let Qt use the OS-native dialog (see module docstring).

    Public so other pickers (e.g. ``cmd_menu._get_open_file_explicit``) share
    the exact same per-desktop policy.
    """
    if sys.platform in ('win32', 'darwin'):
        return True
    return _is_kde()


def _dialog_options():
    """No native flag when native is wanted; DontUseNativeDialog otherwise."""
    if use_native():
        return QFileDialog.Options()
    return QFileDialog.DontUseNativeDialog


def downloads_dir():
    """The user's Downloads folder — the most likely place for a .bin / overlay
    / .plyf — falling back to the home directory when it can't be resolved."""
    try:
        import platformdirs
        d = platformdirs.user_downloads_dir()
        if d and os.path.isdir(d):
            return d
    except Exception:
        pass
    home = os.path.expanduser("~")
    cand = os.path.join(home, "Downloads")
    return cand if os.path.isdir(cand) else home


def _default_directory(directory):
    """Start pickers in Downloads when the caller gave no location.

    - ``""`` → the Downloads folder.
    - a bare suggested filename (no directory part, e.g. ``"pack.plyf"``) →
      that name inside Downloads (used by save dialogs).
    - anything with a directory component / absolute path → left untouched.
    """
    if not directory:
        return downloads_dir()
    if not os.path.dirname(directory):
        return os.path.join(downloads_dir(), directory)
    return directory


def get_open_file_name(parent, caption, directory="", name_filter=""):
    """Drop-in for ``QFileDialog.getOpenFileName`` that uses the native dialog on
    Windows/macOS/KDE and the Qt dialog elsewhere, defaulting to the Downloads
    folder. Returns the ``(path, selected_filter)`` tuple, same as Qt."""
    return QFileDialog.getOpenFileName(
        parent, caption, _default_directory(directory), name_filter,
        options=_dialog_options())


def get_save_file_name(parent, caption, directory="", name_filter=""):
    """Drop-in for ``QFileDialog.getSaveFileName`` that uses the native dialog on
    Windows/macOS/KDE and the Qt dialog elsewhere, defaulting to the Downloads
    folder. Returns the ``(path, selected_filter)`` tuple, same as Qt."""
    return QFileDialog.getSaveFileName(
        parent, caption, _default_directory(directory), name_filter,
        options=_dialog_options())


def _portal_theme_available():
    """True if this Qt build ships the xdg-desktop-portal platform-theme plugin."""
    try:
        import glob
        from PyQt5.QtCore import QLibraryInfo
        plugins = QLibraryInfo.location(QLibraryInfo.PluginsPath)
    except Exception:
        return False
    return bool(glob.glob(os.path.join(plugins, "platformthemes", "*xdgdesktopportal*")))


def maybe_set_portal_platformtheme():
    """On KDE, route Qt's native dialogs through xdg-desktop-portal so the file
    picker is the modern Plasma dialog. Returns True if it set the theme.

    Our pip/venv PyQt5 ships no KDE ``plasma-integration`` plugin, so a plain
    "native" dialog falls back to Qt's old widget dialog even on KDE. The
    bundled Qt *does* ship the xdg-desktop-portal plugin, and KDE runs
    ``xdg-desktop-portal-kde``, so pointing Qt at that theme yields the native
    Plasma picker. **Must be called before the QApplication is constructed.**

    No-op unless: on Linux KDE, ``QT_QPA_PLATFORMTHEME`` unset, and the portal
    platform-theme plugin is present — so it never overrides a user/session
    setting and never names a theme this Qt can't load.
    """
    if sys.platform in ('win32', 'darwin'):
        return False
    if os.environ.get('QT_QPA_PLATFORMTHEME'):
        return False
    if not _is_kde():
        return False
    if not _portal_theme_available():
        return False
    os.environ['QT_QPA_PLATFORMTHEME'] = 'xdgdesktopportal'
    return True
