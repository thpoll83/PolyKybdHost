"""Command & Conquer Generals and Zero Hour: the declaration of this reader.

Light on purpose: the settings and the dialog import it at start. The reader
itself is ``reader.py``; it loads only when an overlay that uses it is first
sent. It reads no pictures, only the key assignments of the installed game.
"""
from polyhost.i18n import N_
from polyhost.services.game_assets.readers import Reader, Setting

READER = Reader(
    module="polyhost.services.game_assets.generals.reader",
    settings=(
        Setting("game_generals_dir", "", N_("Generals folder"), N_(
            "The Command & Conquer Generals or Zero Hour install folder, the one "
            "that holds Game.dat and EnglishZH.big (or the archive of another "
            "language). The overlay then shows the hotkeys of the installed "
            "language and of the player's own CommandMap.ini. Empty: the folder "
            "of the running game and the usual install folders on Windows, in "
            "Steam and under Wine are searched."), None),
    ),
    folder="game_generals_dir",
    variant=None,
)
