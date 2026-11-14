"""Warcraft III (classic, MPQ releases): the declaration of this reader.

Light on purpose: the settings and the dialog import it at start. The reader
itself is ``reader.py``; it loads only when an overlay that uses it is first
sent. It reads no pictures, only the key assignments of the installed game.
"""
from polyhost.i18n import N_
from polyhost.services.game_assets.readers import Reader, Setting

READER = Reader(
    module="polyhost.services.game_assets.warcraft3.reader",
    settings=(
        Setting("game_wc3_dir", "", N_("Warcraft III folder"), N_(
            "The Warcraft III install folder, the one that holds war3.mpq. The "
            "overlay then shows the hotkeys of the installed language and of "
            "the player's CustomKeys.txt. Empty: the folder of the running game "
            "and the usual install folders on Windows, macOS and under Wine are "
            "searched. Reforged keeps its files in a format this app does not "
            "read; the default keys are shown then."), None),
    ),
    folder="game_wc3_dir",
    variant=None,
)
