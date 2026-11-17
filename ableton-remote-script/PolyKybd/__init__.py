# SPDX-License-Identifier: GPL-3.0-or-later
"""PolyKybd remote script for Ableton Live 12.

Live loads this folder from ``<User Library>/Remote Scripts/PolyKybd/`` and
lists it as "PolyKybd" under Settings > Link, Tempo & MIDI > Control Surface.
See ../README.md.
"""


def create_instance(c_instance):
    from .reporter import PolyKybdReporter
    return PolyKybdReporter(c_instance)
