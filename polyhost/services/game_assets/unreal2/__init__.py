"""Unreal Tournament 2004: the declaration of this reader.

Light on purpose: the settings and the dialog import it at start. The reader
itself is ``reader.py``, the package format ``package.py`` and the texture
decoder ``dxt.py``; they load only when an overlay that uses this reader is
first sent.
"""
from polyhost.i18n import N_
from polyhost.services.game_assets.readers import Reader, Setting

READER = Reader(
    module="polyhost.services.game_assets.unreal2.reader",
    settings=(
        Setting("game_ut2004_dir", "", N_("UT2004 folder"), N_(
            "The Unreal Tournament 2004 install folder, the one that holds the "
            "System and Textures folders. Empty: the folder of the running game "
            "and the usual install folders on Windows, Linux, macOS and under "
            "Wine are searched."), None),
    ),
    folder="game_ut2004_dir",
    variant=None,
)
