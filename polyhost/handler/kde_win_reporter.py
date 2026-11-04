import logging
import os
import pathlib
import subprocess
from datetime import datetime

_log = logging.getLogger("PolyHost")


def getActiveWindow():
    script = os.path.join(pathlib.Path(__file__).parent.resolve(), "active_win.js")

    output = (
        subprocess.run(
            "dbus-send --print-reply --dest=org.kde.KWin \
                        /Scripting org.kde.kwin.Scripting.loadScript \
                        string:" + script,
            capture_output=True,
            shell=True,
        )
        .stdout.decode()
        .split("\n")
    )
    reg_script_number = None
    for line in reversed(output):
        if "int32" in line:
            reg_script_number = line.split()[-1]
            break

    if reg_script_number is None:
        _log.warning("KWin: could not find script number in dbus output (transient)")
        return _keep_last("no script number")
    try:
        reg_script_number = str(int(reg_script_number))
    except ValueError:
        _log.warning("KWin: unexpected script number format '%s' (transient)", reg_script_number)
        return _keep_last("bad script number")
    
    datetime_now = datetime.now()
    subprocess.run(
        "dbus-send --print-reply --dest=org.kde.KWin /Scripting/Script"
        + reg_script_number
        + " org.kde.kwin.Script.run",
        shell=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        "dbus-send --print-reply --dest=org.kde.KWin /Scripting/Script"
        + reg_script_number
        + " org.kde.kwin.Script.stop",
        shell=True,
        stdout=subprocess.DEVNULL,
    )

    since = str(datetime_now)

    msg = (
        subprocess.run(
            'journalctl _COMM=kwin_wayland -o cat --since "' + since + '"',
            capture_output=True,
            shell=True,
        )
        .stdout.decode()
        .rstrip()
        .split("\n")
    )
    return read_reply(msg)


# The script's line starts with this; anything else in kwin_wayland's journal
# (KWin's own messages arrive there too) is not the answer.
REPLY_PREFIX = "polykybd-window:"
NO_WINDOW = "none"

# The window of the last good read. ⚠️ A read that finds no reply line is a
# FAILED read, not "no window": the script's print is not always in the
# journal yet when journalctl runs (more often while a game keeps the system
# busy), and reporting None then cleared the keycaps for about a second at a
# time (OpenRA, 2026-11-04). Only the script's explicit "none" means no window.
_last = None


def _keep_last(reason):
    _log.debug("KWin: no reply this cycle (%s); keeping the last window", reason)
    return _last


def read_reply(lines):
    """The active window from the journal lines the script run left: a KWin,
    None when the script reported no active window, or the last window when
    the lines hold no reply (a failed read)."""
    global _last
    replies = [ln.removeprefix("js: ") for ln in lines]
    replies = [ln[len(REPLY_PREFIX):] for ln in replies if ln.startswith(REPLY_PREFIX)]
    if not replies:
        return _keep_last("no reply line")
    reply = replies[-1]
    if reply == NO_WINDOW:
        _last = None
        return None
    try:
        _last = KWin(reply)
    except ValueError as e:
        _log.warning("KWin: malformed window reply (transient): %s", e)
        return _keep_last("malformed reply")
    return _last


class KWin:
    def __init__(self, reply):
        """`reply` is "<class>;<caption>;<pid>"; the caption may contain ";"."""
        name, sep, rest = reply.partition(";")
        title, sep2, pid = rest.rpartition(";")
        if not sep or not sep2:
            raise ValueError(f"Unexpected format reported by KWin Script: '{reply}'")
        self.name = name
        self.title = title
        self.handle = int(pid) if pid else hash(self.name)
        # log = logging.getLogger("PolyHost")
        # log.info("KWin %s", msg)
    
    def getHandle(self):
        return self.handle
    
    def getAppName(self):
        return self.name

    def __eq__(self, other):
        if not other:
            return False
        return self.handle == other.getHandle()


# reporter = KdeWindowReporter()
# win = reporter.getActiveWindow()
# print(f"Title: {win.title} Handle: {win.getHandle()} Name: {win.getAppName()}")
