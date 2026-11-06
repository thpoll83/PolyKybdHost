"""Dune 2000 (1998): the declaration of this reader.

Light on purpose: the settings and the dialog import it at start. The reader
itself is ``reader.py``, the sprite format ``r16.py``; both load only when an
overlay that uses this reader is first sent.
"""
from polyhost.i18n import N_
from polyhost.services.game_assets.readers import Reader, Setting

READER = Reader(
    module="polyhost.services.game_assets.westwood_d2k.reader",
    settings=(
        Setting("game_d2k_data_dir", "", N_("Dune 2000 Folder"), N_(
            "A folder with the Dune 2000 files DATA.R16 (or DATA.R8) and "
            "PALETTE.BIN. Empty: the content folder of OpenRA is searched."), None),
        Setting("game_d2k_house", "atreides", N_("Dune 2000 House"),
                N_("Whose units the OpenRA Dune 2000 overlay shows."),
                (("atreides", N_("Atreides")), ("harkonnen", N_("Harkonnen")),
                 ("ordos", N_("Ordos")))),
    ),
    folder="game_d2k_data_dir",
    variant="game_d2k_house",
)
