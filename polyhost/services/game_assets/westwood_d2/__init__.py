"""Dune II (1992): the declaration of this reader.

Light on purpose: the settings and the dialog import it at start. The reader
itself is ``reader.py``, the archive format ``pak.py``; both load only when an
overlay that uses this reader is first sent.
"""
from polyhost.i18n import N_
from polyhost.services.game_assets.readers import Reader, Setting

READER = Reader(
    module="polyhost.services.game_assets.westwood_d2.reader",
    settings=(
        Setting("game_dune2_data_dir", "", N_("Dune II Folder"), N_(
            "A folder with the original Dune II file DUNE.PAK. Empty: the data "
            "folders of Dune Legacy and OpenDUNE are searched."), None),
        Setting("game_dune2_house", "atreides", N_("Dune II House"),
                N_("Whose units the Dune II overlays show."),
                (("atreides", N_("Atreides")), ("harkonnen", N_("Harkonnen")),
                 ("ordos", N_("Ordos")))),
    ),
    folder="game_dune2_data_dir",
    variant="game_dune2_house",
)
