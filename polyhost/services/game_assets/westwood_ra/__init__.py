"""Red Alert (1996): the declaration of this reader.

Light on purpose: the settings and the dialog import it at start. The reader
itself is ``reader.py``, the archive format ``mix.py``; both load only when an
overlay that uses this reader is first sent.
"""
from polyhost.i18n import N_
from polyhost.services.game_assets.readers import Reader, Setting

READER = Reader(
    module="polyhost.services.game_assets.westwood_ra.reader",
    settings=(
        Setting("game_ra_data_dir", "", N_("Red Alert Folder"), N_(
            "A folder with the classic Red Alert files CONQUER.MIX, HIRES.MIX and "
            "LOCAL.MIX. Empty: the content folder of OpenRA is searched."), None),
        Setting("game_ra_faction", "allies", N_("Red Alert Faction"),
                N_("Whose units and buildings the OpenRA Red Alert overlay shows."),
                (("allies", N_("Allies")), ("soviets", N_("Soviets")))),
    ),
    folder="game_ra_data_dir",
    variant="game_ra_faction",
)
