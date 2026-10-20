"""Install the udev rule that lets a non-root PolyKybdHost open the keyboard on
Linux (``polyhost/device/99-hid.rules``).

The rule file grants the raw HID interface (``hidraw``) and, since the fast
link, the keyboard's serial port (``tty``), and tells ModemManager to leave
that port alone. Without the hidraw lines the app cannot open the keyboard at
all; without the tty lines every transfer silently goes over HID, because the
pipe probe reads "no permission" as "no pipe".

Writing to ``/etc/udev/rules.d`` needs root. The tray offers it as one action
that runs the copy and the ``udevadm`` reload through ``pkexec``, so the user
gets the desktop's PolicyKit password prompt instead of a terminal. The one
line installer (``scripts/install.sh``) writes the same file with ``sudo``.

Qt-free, like every other ``services/`` module: the status check and the
command are unit-tested with fakes, and ``host.py`` only wires the dialogs.
"""
import logging
import platform
import shutil
import subprocess
from pathlib import Path

from polyhost.i18n import M_

log = logging.getLogger(__name__)

RULES_SRC = Path(__file__).resolve().parent.parent / "device" / "99-hid.rules"
RULES_DST = Path("/etc/udev/rules.d/99-hid.rules")

# What rule_status() answers. "stale" means a file is installed but lacks at
# least one rule line of the shipped file (an install from before the tty
# lines, or a hand-edited copy).
STATUS_OK = "ok"
STATUS_MISSING = "missing"
STATUS_STALE = "stale"

# pkexec's own exit codes (pkexec(1)): the user closed the password dialog,
# or PolicyKit refused the authorisation.
PKEXEC_DISMISSED = 126
PKEXEC_NOT_AUTHORISED = 127

# How long the password prompt may stay open before the attempt is given up.
PROMPT_TIMEOUT_S = 300

# Error texts the tray shows; translated there with i18n.translate_message().
# Module constants on purpose, see M_().
MSG_NOT_LINUX = M_("The udev rule is only needed on Linux.")
MSG_NO_PKEXEC = M_("The 'pkexec' command (PolicyKit) is not installed, so the rule cannot be written from here.")
MSG_DISMISSED = M_("The password prompt was closed.")
MSG_NOT_AUTHORISED = M_("PolicyKit refused the authorisation.")
MSG_TIMEOUT = M_("The password prompt was not answered in time.")
MSG_FAILED = M_("The command failed (exit code {code}):\n{output}")
MSG_NOT_STARTED = M_("The command could not be started: {error}")

# Runs as root under pkexec. "$1" and "$2" are the source and the destination,
# passed as arguments so no path is spliced into the shell text. install(1)
# writes the file with mode 0644 whatever the checkout's umask was.
_SHELL_BODY = ('install -m 0644 -- "$1" "$2"'
               ' && udevadm control --reload-rules'
               ' && udevadm trigger')


def is_linux():
    return platform.system() == "Linux"


def rule_lines(text):
    """The rule lines of a rules file: every line that is not blank and not a
    comment, stripped. Comments and order do not matter to udev."""
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def rule_status(src=RULES_SRC, dst=RULES_DST):
    """STATUS_OK when every rule line of ``src`` is in ``dst``, STATUS_STALE
    when ``dst`` exists but lacks one, STATUS_MISSING when it does not exist
    or cannot be read."""
    try:
        installed = set(rule_lines(Path(dst).read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return STATUS_MISSING
    wanted = rule_lines(Path(src).read_text(encoding="utf-8"))
    return STATUS_OK if all(line in installed for line in wanted) else STATUS_STALE


def manual_commands(src=RULES_SRC, dst=RULES_DST):
    """The terminal equivalent, for the dialog that reports a failure."""
    return (f"sudo install -m 0644 '{src}' '{dst}'\n"
            "sudo udevadm control --reload-rules && sudo udevadm trigger")


def install_command(src=RULES_SRC, dst=RULES_DST, pkexec="pkexec"):
    """The argv that installs the rule as root: pkexec, a shell with the fixed
    body above, and the two paths as positional arguments ($1, $2)."""
    return [pkexec, "sh", "-c", _SHELL_BODY, "polyhost-udev", str(src), str(dst)]


def install_rules(src=RULES_SRC, dst=RULES_DST, run=subprocess.run, which=shutil.which):
    """Install the rule through pkexec. Blocks while the password prompt is
    open, so call it from a worker thread. Returns ``(ok, error)``; ``error``
    is an English message built from an ``M_()`` template, or "" on success."""
    if not is_linux():
        return False, MSG_NOT_LINUX
    pkexec = which("pkexec")
    if not pkexec:
        return False, MSG_NO_PKEXEC
    argv = install_command(src, dst, pkexec)
    log.info("Installing the udev rule: %s", " ".join(argv[:3] + ["…"] + argv[-2:]))
    try:
        # Audit (Sourcery dangerous-subprocess-use): argv is a fixed list, the
        # shell body is a module constant, and the only variable parts are the
        # two paths, passed as separate arguments that the body reads as "$1"
        # and "$2". Nothing from the user or the network reaches the command.
        # nosemgrep
        proc = run(argv, capture_output=True, text=True, timeout=PROMPT_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return False, MSG_TIMEOUT
    except OSError as exc:
        return False, MSG_NOT_STARTED.format(error=exc)
    if proc.returncode == 0:
        log.info("udev rule installed to %s", dst)
        return True, ""
    if proc.returncode == PKEXEC_DISMISSED:
        return False, MSG_DISMISSED
    if proc.returncode == PKEXEC_NOT_AUTHORISED:
        return False, MSG_NOT_AUTHORISED
    output = (proc.stderr or proc.stdout or "").strip()
    log.warning("udev rule install failed (exit %d): %s", proc.returncode, output)
    return False, MSG_FAILED.format(code=proc.returncode, output=output)
