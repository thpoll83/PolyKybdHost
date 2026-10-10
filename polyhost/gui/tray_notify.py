"""Whether a tray balloon actually REACHES the user — and the menu/tooltip
marker that carries a pending update when it does not.

⚠️ **`QSystemTrayIcon.showMessage` is a silent no-op on macOS as we ship
today.** Qt's Cocoa backend routes it through ``NSUserNotificationCenter``,
which drops a notification whose calling process has no bundle identifier of
its own: no banner, no exception, and ``messageClicked`` never fires — so the
click-the-balloon-to-install path dies with it. PolyHost is always a bare
``python -m polyhost`` there. The LaunchAgent's ``ProgramArguments`` is the
shell wrapper, and even ``~/Applications/PolyHost.app`` is a shim that ``exec``s
that same wrapper (`services/add_to_startup.py`), so ``NSBundle.mainBundle``
resolves to the Python framework rather than to ``com.PolyHost``.

Hence the test below is the real rule ``NSBundle`` applies — is the running
executable inside ``<name>.app/Contents/MacOS/``? — and not a flat
``sys.platform == "darwin"``. Ship a genuine bundle one day and balloons come
back on their own, with nothing here to remember to revert.

The fallback is two things, because either alone is too weak: the update flow
opens its confirmation dialog directly instead of waiting for a click that can
never arrive, and the top-level ``Updates`` tray row carries the version, since
the row that used to carry it sits one submenu deeper than anyone looks.
"""
import sys
from pathlib import PurePath

from polyhost.i18n import _, _f


def balloons_are_delivered(platform_name=None, executable=None):
    """True when ``QSystemTrayIcon.showMessage`` reaches the user here.

    Answers for the PROCESS, not for the OS: the same macOS shows balloons for
    a bundled app and drops them for this one.
    """
    if (platform_name or sys.platform) != "darwin":
        return True
    return _inside_app_bundle(executable if executable is not None else sys.executable)


def _inside_app_bundle(executable):
    """True when `executable` sits at ``<name>.app/Contents/MacOS/<exe>``.

    Deliberately NOT resolved through symlinks: what decides the process's
    bundle is the path it was launched as, which is what ``sys.executable``
    holds.
    """
    try:
        parts = PurePath(executable).parts
    except TypeError:
        return False
    return (len(parts) >= 4
            and parts[-2] == "MacOS"
            and parts[-3] == "Contents"
            and parts[-4].endswith(".app"))


def _pending_sentence(prefix, host_version, fw_version):
    """`prefix` followed by the pending versions, as ONE translatable sentence
    per combination (a translator cannot reorder a list joined in code)."""
    if host_version and fw_version:
        return _f("{prefix} — host v{host_version}, firmware v{fw_version} available",
                  prefix=prefix, host_version=host_version, fw_version=fw_version)
    if host_version:
        return _f("{prefix} — host v{host_version} available",
                  prefix=prefix, host_version=host_version)
    if fw_version:
        return _f("{prefix} — firmware v{fw_version} available",
                  prefix=prefix, fw_version=fw_version)
    return ""


def updates_menu_title(host_version=None, fw_version=None, base=None):
    """Text for the top-level ``Updates`` tray row.

    Where a balloon is dropped this row is the ONLY thing announcing a new
    version, so it names the version rather than hinting that something is
    inside.
    """
    if base is None:
        base = _("Updates")
    return _pending_sentence(base, host_version, fw_version) or base


def updates_tooltip(host_version=None, fw_version=None):
    """Tray-icon tooltip for pending updates; ``""`` when there are none."""
    return _pending_sentence("PolyKybd", host_version, fw_version)
