# SPDX-License-Identifier: GPL-3.0-or-later
"""PolyKybd Context Reporter for QGIS. See README.md."""


def classFactory(iface):  # noqa: N802 -- the name QGIS calls
    from .plugin import PolyKybdContextReporter
    return PolyKybdContextReporter(iface)
