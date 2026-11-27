"""Whether a plain launch starts as a forwarder: the `start_as_forwarder` setting.

A forwarder runs on a computer with no keyboard and reports its windows to the keyboard
computer. It used to need a command-line option (`--host`, `--host-file` or
`--detect-host`), which a person has to know and an autostart entry has to carry. The
setting makes it a choice in the tray menu: "Switch to Forwarder" sets it and restarts,
"Switch to Keyboard mode" clears it and restarts. The autostart launchers (a Windows task,
a Linux .desktop file, a macOS launchd plist) are not touched, and `python -m polyhost`
with no options follows the setting.

The setting is only the default for a plain launch. An option that names a mode wins:
`--host`, `--host-file`, `--detect-host`, `--headless` and `--connect`, and
`--no-forwarder` turns the setting off for one run. ⚠️ `--headless` and `--connect` must
win: the tray starts its background daemon with `--headless`, and a setting that turned
that daemon into a forwarder would take the keyboard away.

Qt-free: `main_app` reads it before any Qt import.
"""
from __future__ import annotations

import os

SETTING = "start_as_forwarder"
#: A file in the config folder, made by the switch and removed by the forwarder it starts:
#: that forwarder offers to pair once. A setting would have to be listed and labelled in
#: the dialog, and this is not something a person edits.
_PAIR_PROMPT_FILE = "forwarder_pair_prompt"


def forwarder_from_setting(*, host=None, host_file=None, detect_host=False,
                           headless=False, connect=None, no_forwarder=False,
                           setting=False) -> bool:
    """True when this launch is a forwarder because of the setting alone.

    `connect` is `args.connect`: None when the option is absent, a string (maybe empty)
    when it is given."""
    explicit = bool(host or host_file or detect_host or headless or connect is not None)
    return bool(setting) and not explicit and not no_forwarder


def _is_option(arg: str, full: str) -> bool:
    """True when `arg` is `full` or an abbreviation of it, with or without `=value`.

    argparse accepts any unambiguous prefix (`--no-for`), and `argv` reached here only
    after it parsed, so a prefix of `full` that parsed was not ambiguous."""
    name = arg.split("=", 1)[0]
    return len(name) > 2 and name.startswith("--") and full.startswith(name)


def strip_options(argv, *, connect=False, no_forwarder=True):
    """A copy of `argv` without the options that must not outlive one run.

    `--no-forwarder` ("ignore the setting for this run") must not reach a launcher or a
    relaunch that is meant to follow the setting. `--connect [ENDPOINT]` makes a keyboard
    client, which the switch to a forwarder replaces. Abbreviations of both count."""
    out, skip_value = [], False
    for arg in argv:
        if skip_value:
            skip_value = False
            if not arg.startswith("-"):
                continue            # the endpoint that followed --connect
        if no_forwarder and _is_option(arg, "--no-forwarder"):
            continue
        if connect and _is_option(arg, "--connect"):
            skip_value = "=" not in arg     # nargs="?": an endpoint may follow
            continue
        out.append(arg)
    return out


def set_start_as_forwarder(settings, enabled: bool, source: str) -> bool:
    """Write the setting through `settings` (a PolySettings). Returns whether it was
    saved. Switching on also leaves the one-shot "offer to pair" marker."""
    current = dict(settings.get_all())
    current[SETTING] = bool(enabled)
    saved = settings.set_all(current, source=source)
    if saved and enabled:
        mark_pair_prompt()
    return bool(saved)


def _marker_path() -> str:
    from polyhost.settings import settings_path
    return os.path.join(os.path.dirname(settings_path()), _PAIR_PROMPT_FILE)


def mark_pair_prompt() -> None:
    try:
        with open(_marker_path(), "w", encoding="utf-8") as handle:
            handle.write("1")
    except OSError:
        pass            # the offer is a convenience: the menu item is still there


def take_pair_prompt() -> bool:
    """True once after a switch: the forwarder should offer to pair now."""
    path = _marker_path()
    if not os.path.exists(path):
        return False
    try:
        os.remove(path)
    except OSError:
        return False
    return True
