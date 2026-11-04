#!/usr/bin/env python3
"""Warzone 2100 units for the overlay, as body + propulsion + turret.

Each entry is drawn by `cnc_remastered/wz_units.render()` from the game's own
models and textures (GPL-2.0-or-later, fetched from pinned commits). The ten
control-group units are the ones the C&C Remastered set uses; the rest show
the unit type of a "select all" key.

⚠️ `prm[lr]whl1.pie` (the left and right wheels) are CC BY-SA 3.0 in Warzone's
`COPYING.NONGPL`; the plain `prmwhl1.pie` used here is GPL. The weapon texture
`page-17-droid-weapons.png` is CC BY-SA 3.0 as well (see SOURCES.md).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import wz_units  # noqa: E402

B, M = wz_units.B, wz_units.M


def _droid(body: str, prop: str, mount: str | None, gun: str | None, yaw=60, pitch=25):
    parts = [(f"{B}/bodies/{body}", (0, 0, 0)), (f"{B}/prop/{prop}", (0, 0, 0))]
    parts += [(f"{B}/weapons/{p}", "body-connector") for p in (mount, gun) if p]
    return parts, dict(yaw=yaw, pitch=pitch)


# name: (label, parts, camera)
MODELS = {f"group{d}": (label, parts, cam) for d, (label, parts, cam) in wz_units.UNITS.items()}
MODELS.update({
    "tracks": ("Tracks, machine gun", *_droid("drmbod06.pie", "prmtrk2.pie", "trmmg.pie", "gnmmg1.pie")),
    "halftracks": ("Half-tracks, machine gun", *_droid("drmbod06.pie", "prmhtr2.pie", "trmmg.pie", "gnmmg1.pie")),
    "wheels": ("Wheels, machine gun", *_droid("drmbod06.pie", "prmwhl1.pie", "trmmg.pie", "gnmmg1.pie")),
    "hovers": ("Hover, machine gun", *_droid("drmbod06.pie", "prmhov1.pie", "trmmg.pie", "gnmmg1.pie")),
    "vtols": ("VTOL, lancer", *_droid("drmbod06.pie", "prmvtl1.pie", "trmlas.pie", "gnmrlas.pie", pitch=45)),
    "trucks": ("Truck", *_droid("drmbod05.pie", "prmwhl1.pie", None, "trmcon.pie", yaw=120)),
    "repairtanks": ("Repair turret", *_droid("drmbod05.pie", "prmwhl1.pie", "trmecm1.pie", "gnmrepar.pie", yaw=120)),
    "sensors": ("Sensor turret", *_droid("drmbod05.pie", "prmwhl1.pie", "trmsnsr2.pie", "gnmsnsr2.pie", yaw=120)),
    "commander": ("Command turret", *_droid("drmbod06.pie", "prmtrk2.pie", "trlcmd1.pie", "gnlcmd1.pie")),
    "heavytank": ("Heavy tank, cannon (land combat)", *_droid("drhbod09.pie", "prhtrk3.pie", "trhcan.pie", "gnhcan.pie")),
    "transporters": ("Transport", [(f"{B}/bodies/drtrans.pie", (0, 0, 0))], dict(yaw=60, pitch=30)),
    "cyborgs": ("Cyborg, machine gun", [(f"{B}/bodies/cybd_std.pie", (0, 0, 0)),
                                         (f"{B}/weapons/cy_gun.pie", "body-connector")], dict(yaw=30, pitch=15)),
})


def render(name: str, px: int = 160):
    """(grey 0..1, coverage) of model `name`; `name@yaw,pitch` overrides its camera."""
    name, _, view = name.partition("@")
    _label, parts, cam = MODELS[name]
    if view:
        yaw, pitch = (float(v) for v in view.split(","))
        cam = dict(cam, yaw=yaw, pitch=pitch)
    return wz_units.render(parts, px=px, **cam)
