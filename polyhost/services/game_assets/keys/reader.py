"""The ``keys`` reader: no game art, only the player's key bindings.

``find()`` never finds files, so ``build.build`` hands the spec to
``build.keys_only``, which reads the spec's ``bindings:`` source and moves the
shipped icons. The other functions exist because ``build`` expects a reader to
have them; none of them is reached for this reader.
"""
from __future__ import annotations

from pathlib import Path


def find(folder: str = "", hint=None) -> None:
    """No art is read for these games."""
    return None


def searched(hint=None) -> list[Path]:
    """No folder is searched for art (the log line says "no folder")."""
    return []


def fingerprint(files: dict) -> list:
    return []


def open_source(files: dict):
    return None


def draw(src, recipe: dict, size):
    raise ValueError("the keys reader draws no pictures")
