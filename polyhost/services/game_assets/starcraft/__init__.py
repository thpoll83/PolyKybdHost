"""StarCraft (1998) and Brood War: the declaration of this reader.

Light on purpose: the settings and the dialog import it at start. The reader
itself is ``reader.py``, the file formats ``mpq.py``, ``explode.py`` and
``grp.py``; they load only when an overlay that uses this reader is first sent.
"""
from polyhost.i18n import N_
from polyhost.services.game_assets.readers import Reader, Setting

READER = Reader(
    module="polyhost.services.game_assets.starcraft.reader",
    settings=(
        Setting("game_sc1_data_dir", "", N_("StarCraft Folder"), N_(
            "A folder with the StarCraft 1.16.1 files StarDat.mpq and, for the "
            "Brood War units, BrooDat.mpq. Empty: the usual install folders on "
            "Windows, macOS and under Wine are searched. StarCraft: Remastered "
            "keeps its files in a format this app does not read; the shipped "
            "art is used then."), None),
        Setting("game_sc1_race", "terran", N_("StarCraft Race"),
                N_("Whose units the StarCraft II overlay shows when it draws them "
                   "from the StarCraft files."),
                (("terran", N_("Terran")), ("protoss", N_("Protoss")), ("zerg", N_("Zerg")))),
    ),
    folder="game_sc1_data_dir",
    variant="game_sc1_race",
)
