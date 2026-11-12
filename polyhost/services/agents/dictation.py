"""Start the operating system's dictation from the '-' key in AI mode.

The host sends the dictation shortcut as key presses into whatever window has the
focus, as if the user typed it. The shortcut is the setting
`agents_dictation_shortcut` in pynput's hotkey syntax (`<cmd>+h`, `<ctrl>+<alt>+d`).
Empty means the OS default:

- Windows: Win+H (Windows voice typing).
- macOS: none. Its default shortcut is a double press of Fn or Control, which a
  program cannot send; set a shortcut in System Settings > Keyboard > Dictation and
  enter it here.
- Linux: none. There is no standard dictation; enter the shortcut of the tool you use.
"""
from __future__ import annotations

import sys
import time

DEFAULT_SHORTCUTS = {"win32": "<cmd>+h"}


def shortcut_for(setting: str | None, platform: str = sys.platform) -> str:
    """The shortcut to send: the setting, else the OS default, else ''."""
    setting = (setting or "").strip()
    if setting:
        return setting
    return DEFAULT_SHORTCUTS.get(platform, "")


def send_shortcut(shortcut: str, controller=None, delay_s: float = 0.15) -> bool:
    """Press and release `shortcut`. False when there is nothing to send or pynput
    cannot parse it. The short delay lets the keyboard's own key release (the '-'
    key) reach the OS first, so the two do not overlap."""
    if not shortcut:
        return False
    from pynput import keyboard
    try:
        keys = keyboard.HotKey.parse(shortcut)
    except ValueError:
        return False
    controller = controller or keyboard.Controller()
    time.sleep(delay_s)
    for key in keys:
        controller.press(key)
    for key in reversed(keys):
        controller.release(key)
    return True
