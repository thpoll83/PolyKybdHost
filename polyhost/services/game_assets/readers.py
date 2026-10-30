"""The game-asset readers this host has, and the settings each one adds.

Each reader is a subfolder of ``game_assets`` (``westwood_td/``): its
``__init__.py`` declares a ``Reader`` and the reader's own modules sit beside it.

An overlay opts in with ``game_assets: <spec>`` in its overlay-mapping entry;
the spec's ``game_assets:`` block names the reader and says what to draw on
each key (see ``overlay_sources/cnc_remastered/cnc_remastered.yaml``). Each
reader declares its own settings; ``polyhost/settings.py`` merges the defaults
and the settings dialog shows the rows, so adding a reader expands the settings.

This module stays light: it is imported by the settings and the dialog at
start, before anyone knows whether a game is installed. The reader itself
(numpy, PIL) is imported only when an overlay that uses it is first sent.
"""
from __future__ import annotations

from collections import namedtuple

# key: the settings key; default: its value when unset; label and description:
# shown in the settings dialog; choices: ((value, label), ...) for a dropdown.
Setting = namedtuple("Setting", "key default label description choices")

# module: the reader's implementation, imported on first use; settings: what it
# adds; folder: the setting with a folder to read from (empty = search);
# variant: the setting whose value picks a per-variant entry in a spec's icons.
Reader = namedtuple("Reader", "module settings folder variant")


def _registry() -> dict:
    """{name: Reader}. Each reader is a subfolder of game_assets whose
    ``__init__.py`` declares ``READER``; add a new one here."""
    from polyhost.services.game_assets import westwood_d2, westwood_d2k, westwood_ra, westwood_td
    return {"westwood_td": westwood_td.READER, "westwood_ra": westwood_ra.READER,
            "westwood_d2": westwood_d2.READER, "westwood_d2k": westwood_d2k.READER}


READERS = _registry()


def all_settings() -> list:
    """Every reader's settings, in declaration order."""
    return [s for r in READERS.values() for s in r.settings]


def reader_defaults() -> dict:
    """{key: default} of every reader setting, for DEFAULT_SETTINGS."""
    return {s.key: s.default for s in all_settings()}
