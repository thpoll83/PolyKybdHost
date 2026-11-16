# SPDX-License-Identifier: GPL-3.0-or-later
# PolyKybd context reporter for FreeCAD: tells the local PolyKybdHost which
# workbench is active. No workbench of its own. See README.md.
# FreeCAD runs this file with exec() at GUI start and puts this folder on
# sys.path, so the module below is imported by name.
try:
    import polykybd_freecad_gui
    polykybd_freecad_gui.start()
except Exception as _pk_error:  # noqa: BLE001 -- never stop FreeCAD's start
    import FreeCAD
    FreeCAD.Console.PrintWarning(f"PolyKybd reporter not started: {_pk_error}\n")
