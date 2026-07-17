"""Shared file-dialog helpers that force the Qt (non-native) picker on Linux.

Qt's ``QFileDialog`` static helpers use the OS-native picker by default. On
Linux that means the GTK / KDE / xdg-desktop-portal dialog, whose look and
behaviour drift from the rest of this PyQt5 app (and which can misbehave under
some portals). We want the Qt dialog on Linux everywhere; Windows and macOS
keep their native picker, which is the expected platform look there.

Route every open/save picker through these wrappers instead of calling
``QFileDialog.getOpenFileName`` / ``getSaveFileName`` directly. They call the
same static methods (so unit tests that patch ``QFileDialog.getOpenFileName``
still work), only adding the ``DontUseNativeDialog`` option on Linux.

``cmd_menu._get_open_file_explicit`` is a richer variant (it also defeats
KDE's single-click-to-accept); it likewise forces the Qt dialog on Linux.
"""
import sys

from PyQt5.QtWidgets import QFileDialog


def _linux_qt_options():
    """DontUseNativeDialog on Linux (force the Qt picker); no-op elsewhere."""
    if sys.platform in ('win32', 'darwin'):
        return QFileDialog.Options()
    return QFileDialog.DontUseNativeDialog


def get_open_file_name(parent, caption, directory="", name_filter=""):
    """Drop-in for ``QFileDialog.getOpenFileName`` that uses the Qt dialog on
    Linux. Returns the ``(path, selected_filter)`` tuple, same as Qt."""
    return QFileDialog.getOpenFileName(
        parent, caption, directory, name_filter, options=_linux_qt_options())


def get_save_file_name(parent, caption, directory="", name_filter=""):
    """Drop-in for ``QFileDialog.getSaveFileName`` that uses the Qt dialog on
    Linux. Returns the ``(path, selected_filter)`` tuple, same as Qt."""
    return QFileDialog.getSaveFileName(
        parent, caption, directory, name_filter, options=_linux_qt_options())
