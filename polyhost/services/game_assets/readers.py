"""The game-asset readers this host has, and the settings each one adds.

An overlay opts in with ``game_assets: <spec>`` in its overlay-mapping entry;
the spec's ``game_assets:`` block names the reader and says what to draw on
each key (see ``overlay_sources/cnc_remastered/cnc_remastered.yaml``). Each
reader adds its own settings here: ``polyhost/settings.py`` merges the defaults
and the settings dialog shows the rows, so adding a reader expands the settings.

This module stays light: it is imported by the settings and the dialog at
start, before anyone knows whether a game is installed. The reader itself
(numpy, PIL) is imported only when an overlay that uses it is first sent.
"""
from __future__ import annotations

from collections import namedtuple

from polyhost.i18n import N_

# key: the settings key; default: its value when unset; label and description:
# shown in the settings dialog; choices: ((value, label), ...) for a dropdown.
Setting = namedtuple("Setting", "key default label description choices")

# module: the reader's implementation, imported on first use; settings: what it
# adds; folder: the setting with a folder to read from (empty = search);
# variant: the setting whose value picks a per-variant entry in a spec's icons.
Reader = namedtuple("Reader", "module settings folder variant")

READERS = {
    # Command & Conquer (1995) and the classic files the Remastered Collection keeps.
    "westwood_td": Reader(
        module="polyhost.services.game_assets.westwood_td",
        settings=(
            Setting("game_cnc_data_dir", "", N_("Command and Conquer Folder"), N_(
                "A folder with the classic Command & Conquer files CONQUER.MIX and "
                "TEMPERAT.MIX. Empty: the Steam and EA app installs of the Remastered "
                "Collection are searched."), None),
            Setting("game_cnc_faction", "gdi", N_("Command and Conquer Faction"),
                    N_("Whose units and buildings the C&C Remastered overlay shows."),
                    (("gdi", N_("GDI")), ("nod", N_("Nod")))),
        ),
        folder="game_cnc_data_dir",
        variant="game_cnc_faction",
    ),
}


def all_settings() -> list:
    """Every reader's settings, in declaration order."""
    return [s for r in READERS.values() for s in r.settings]


def reader_defaults() -> dict:
    """{key: default} of every reader setting, for DEFAULT_SETTINGS."""
    return {s.key: s.default for s in all_settings()}
