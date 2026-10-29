"""Command & Conquer (Tiberian Dawn, 1995): the declaration of this reader.

Light on purpose: the settings and the dialog import it at start. The reader
itself is ``reader.py`` (numpy, PIL), the file formats are ``westwood.py``;
both load only when an overlay that uses this reader is first sent.
"""
from polyhost.i18n import N_
from polyhost.services.game_assets.readers import Reader, Setting

READER = Reader(
    module="polyhost.services.game_assets.westwood_td.reader",
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
)
