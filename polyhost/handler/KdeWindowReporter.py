# import logging
import os
import pathlib
import subprocess
from datetime import datetime


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
        raise Exception(f"Could not find KWin Script: '{output}'")
    
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
    msg = [elem.removeprefix("js: ") for elem in msg]

    return KWin(msg[0])


class KWin:
    def __init__(self, msg):
        elems = msg.split(";")
        if len(elems) != 2:
            raise Exception(f"Unexpected format reported by KWin Script: '{msg}'")
        self.title = elems[1]
        self.name = elems[0] 
        self.handle = hash(msg)
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
