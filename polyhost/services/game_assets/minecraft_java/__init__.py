"""Minecraft: Java Edition: the declaration of this reader.

Light on purpose: the settings and the dialog import it at start. The reader
itself is ``reader.py`` (numpy, PIL, zipfile); it loads only when an overlay
that uses this reader is first sent.
"""
from polyhost.i18n import N_
from polyhost.services.game_assets.readers import Reader, Setting

READER = Reader(
    module="polyhost.services.game_assets.minecraft_java.reader",
    settings=(
        Setting("game_minecraft_dir", "", N_("Minecraft Folder"), N_(
            "The Minecraft: Java Edition game folder, the one with the versions "
            "folder. The item pictures are read from the newest release installed "
            "there. Empty: the standard game folder of the Minecraft Launcher is "
            "searched."), None),
    ),
    folder="game_minecraft_dir",
    variant=None,
)
