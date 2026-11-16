"""The reader for a game whose overlay follows the player's key bindings and
draws no art from the game: the declaration of this reader.

A spec names it with ``reader: keys`` and its bindings source with
``bindings: <name>`` (the module ``game_assets/<name>_keys.py``). The reader
finds no game files, so ``build.build`` always takes the ``build.keys_only``
path: the shipped overlay, with its icons moved to the player's keys. It adds
no settings: each bindings source searches the game's usual folders itself.
"""
from polyhost.services.game_assets.readers import Reader

READER = Reader(
    module="polyhost.services.game_assets.keys.reader",
    settings=(),
    folder=None,
    variant=None,
)
