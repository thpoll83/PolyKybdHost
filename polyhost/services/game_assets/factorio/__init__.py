"""Factorio (2.0 and later): the declaration of this reader.

Light on purpose: the settings and the dialog import it at start. The reader
itself is ``reader.py`` (numpy, PIL); it loads only when an overlay that uses
this reader is first sent.
"""
from polyhost.i18n import N_
from polyhost.services.game_assets.readers import Reader, Setting

READER = Reader(
    module="polyhost.services.game_assets.factorio.reader",
    settings=(
        Setting("game_factorio_data_dir", "", N_("Factorio Folder"), N_(
            "The data folder of a Factorio install, the folder with base and core "
            "in it. Empty: the Steam libraries and the standard install folders "
            "are searched."), None),
    ),
    folder="game_factorio_data_dir",
    variant=None,
)
