"""Firmware updates that change the keyboard's STORED keymap.

A stored keymap takes priority over the firmware's defaults, so a changed default
key reaches an existing board only through a one-time migration in the firmware
(qmk_firmware KEYMAP_STORAGE.md, "One-time migrations"). The migration changes
only keys that still hold the old default; remapped keys and macros stay.

The update dialog names these changes before the user flashes. Each entry is the
first firmware version that runs the migration (the version its merge received,
which every later release contains) and the sentence the dialog shows. Add one
entry per new KEYMAP_MIG_* value in the firmware.
"""
from polyhost.i18n import N_
from polyhost.services.preview_data import parse_version

KEYMAP_CHANGES = (
    # KEYMAP_MIG_AI_KEY (qmk_firmware #433)
    ("1.13.1", N_("The Hyper key on the QWERTY, Stag, Colemak DH and Workman layouts "
                  "becomes the AI key.")),
)


def keymap_changes(installed, target) -> list:
    """The untranslated sentences of every keymap change an update from
    `installed` to `target` brings. An unknown installed version counts as
    older than every entry: the migration changes nothing on a board that
    already had it, so naming it once too often is harmless."""
    target_v = parse_version(target)
    installed_v = parse_version(installed) if installed else (-1,)
    return [text for version, text in KEYMAP_CHANGES
            if installed_v < parse_version(version) <= target_v]
