"""The Qt half of the UI language: where the OS language comes from, the
layout direction, and Qt's own translations for its standard buttons.

``polyhost.i18n`` holds everything that does not need Qt. ``main_app`` calls
:func:`prepare` before either tray app is constructed and
:func:`install_qt_translator` right after, so the tray app and the forwarder
get the same treatment from one place.
"""

import logging
import os

from PyQt5.QtCore import QLibraryInfo, QLocale, Qt, QTranslator
from PyQt5.QtWidgets import QApplication, QMessageBox

from polyhost import i18n
from polyhost.i18n import _

_log = logging.getLogger(__name__)

def os_ui_languages():
    """The OS user-interface languages, most preferred first.

    ⚠️ Not ``locale.getlocale()`` (on Windows that is the regional FORMAT
    setting) and not the input layout (this app switches that itself on every
    Lang key). Qt reads the right source on each platform:
    GetUserDefaultUILanguages on Windows, AppleLanguages on macOS, and
    LANGUAGE / LC_ALL / LC_MESSAGES / LANG on Linux.
    """
    try:
        return [str(tag) for tag in QLocale.system().uiLanguages()]
    except Exception as e:  # noqa: BLE001 -- English is always a valid answer
        _log.warning("Could not read the OS UI languages: %s", e)
        return []


def prepare(setting):
    """Resolve and install the UI language. Call BEFORE the first widget exists:
    the layout direction is read when a widget is created."""
    os_langs = os_ui_languages()
    code = i18n.resolve(setting, os_langs, os.environ.get(i18n.ENV_OVERRIDE))
    i18n.install(code)
    QApplication.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl(code) else Qt.LeftToRight)
    _log.info("UI language: %s (setting %r, OS %s)", code, setting, ", ".join(os_langs[:3]) or "-")
    return code


def install_qt_translator(app, code=None):
    """Load Qt's own catalog (Cancel, Yes, the file dialog) for ``code``.

    Needs the QApplication instance. Qt ships no catalog for Vietnamese or
    Indonesian; their standard buttons stay English.
    """
    code = code or i18n.current_language()
    if code in (i18n.SOURCE_LANGUAGE, i18n.PSEUDO):
        return False
    # Parented to the app, so Qt owns it for the life of the process; a
    # Python reference to keep it alive is not needed.
    translator = QTranslator(app)
    path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    for name in (f"qtbase_{code}", f"qtbase_{code.split('_')[0]}"):
        if translator.load(name, path):
            app.installTranslator(translator)
            # Loading the catalog can flip the direction (Qt reads it from
            # the catalog itself); ours is the answer.
            app.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl(code) else Qt.LeftToRight)
            return True
    _log.info("Qt ships no %s catalog; standard buttons stay English.", code)
    return False


def language_change_needs_restart(new_setting):
    """True when ``new_setting`` resolves to a language other than the one
    this process is showing. A change from "auto" to the language the OS
    already gives needs nothing."""
    target = i18n.resolve(new_setting, os_ui_languages(), os.environ.get(i18n.ENV_OVERRIDE))
    return target != i18n.current_language()


def offer_language_restart(new_setting, restart):
    """Ask whether to restart now when the language setting changed, and call
    ``restart`` on yes. Strings are read once at startup, so a live switch
    would need every open widget to re-set its text; a tray restart is cheap
    (the daemon keeps the keyboard)."""
    if not language_change_needs_restart(new_setting):
        return False
    answer = QMessageBox.question(
        None, _("Language"),
        _("The new language is used after a restart. Restart now?"),
        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
    if answer == QMessageBox.Yes:
        restart()
        return True
    return False
