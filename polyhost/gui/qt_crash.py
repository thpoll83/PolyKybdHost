"""Qt-side half of the crash capture (see :mod:`polyhost.util.crash_log`).

Qt writes its own diagnostics — including the ``qFatal()`` message PyQt5 emits
just before aborting on an unhandled exception in a slot — to stderr, which is a
silent no-op under ``pythonw.exe``. ``qInstallMessageHandler`` redirects them
into our log, so the last thing Qt said before a process vanished is on disk.

It also surfaces the quieter class of Qt complaint that used to go nowhere, e.g.
``QSystemTrayIcon::setVisible: No Icon set`` — exactly the kind of line that
would have shortened a missing-tray-icon investigation.
"""
import logging


def install_qt_message_handler(log=None):
    """Route Qt's own messages into ``log``. Best effort; never raises."""
    log = log or logging.getLogger("PolyHost")
    try:
        from PyQt5.QtCore import QtMsgType, qInstallMessageHandler
    except Exception as e:  # noqa: BLE001 — a missing symbol must not stop startup
        log.warning("Qt message handler not installed (%s: %s).", type(e).__name__, e)
        return False

    levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    def _handler(msg_type, context, message):
        level = levels.get(msg_type, logging.WARNING)
        try:
            log.log(level, "Qt: %s", message)
            if level >= logging.CRITICAL:
                # qFatal aborts immediately after this returns — get it out of
                # the buffers and mark the crash file while we still can.
                from polyhost.util import crash_log
                crash_log._stamp("Qt fatal: %s" % message)
                crash_log._flush_logging()
        except Exception:  # noqa: BLE001
            pass

    qInstallMessageHandler(_handler)
    return True
