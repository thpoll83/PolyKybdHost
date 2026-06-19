"""Diagnostics for the daylight-dependent keycap brightness.

Run on the machine the keyboard is attached to:

    python -m polyhost.services.brightness_diag

It reproduces the exact pipeline that the 10-min worker periodic
(`PolyCore._brightness_periodic`) drives — `Sunlight.get_brightness_now()`
→ device value `2 + normalized * 48` — and prints, path by path, *why* a
given device value comes out, so a "stuck at 2" report can be traced to a
concrete cause (night, a mis-scaled curve, a failed online lookup, or the
clear-sky timezone bug) instead of guessed at.

It only reads — it never talks to the keyboard and changes no settings.
"""

import math
from datetime import datetime, timezone, timedelta

from polyhost.settings import PolySettings
from polyhost.services.sunlight_helper import Sunlight


def device_value(normalized, gamma=1.0):
    """The mapping PolyCore applies: normalized 0..1 -> device 2..50, with the
    perceptual gamma applied first (gamma=1.0 is the legacy linear behaviour).
    The firmware then writes (value-1) straight to the SSD1306 contrast register
    (linear, capped at 49) — so the perceptual shaping lives entirely here."""
    if gamma and gamma > 0:
        normalized = normalized ** gamma
    return 2 + normalized * 48


def normalize(irradiance, min_val, max_val, pre_scale):
    """Mirror of Sunlight.get_brightness_now's normalization (no logging)."""
    perceived = math.log(1 + irradiance) * pre_scale
    span = max_val - min_val
    if span <= 0:                      # degenerate config — avoid div-by-zero
        return perceived, 0.0
    normalized = (max(min_val, min(max_val, perceived)) - min_val) / span
    return perceived, normalized


def curve_analysis(min_val, max_val, pre_scale, gamma=1.0):
    print("=" * 72)
    print("1. CALIBRATION — irradiance -> device brightness curve")
    print("=" * 72)
    print(f"   settings: irradiance_min={min_val}  irradiance_max={max_val}  "
          f"prescaler={pre_scale}  brightness_gamma={gamma}")
    print(f"   formula : perceived = ln(1+irr) * {pre_scale}")
    print( "             normalized = clamp(perceived, min, max) mapped to 0..1")
    print(f"             device    = 2 + normalized**{gamma} * 48   (int-clipped 0..50)")
    print( "             firmware writes (device-1) straight to the OLED contrast")
    print( "             register, linear and capped at 49 (burn-in headroom).\n")

    # Detect degenerate configs that pin the output before computing the
    # physical break-points (which would divide by a zero prescaler).
    if pre_scale <= 0:
        print("   [!!] prescaler is <= 0  ->  perceived = ln(1+irr) * 0 = 0 for")
        print("        EVERY irradiance, so brightness is ALWAYS pinned to the")
        print("        floor (device value 2) no matter how bright it is outside.")
        print("        THIS is almost certainly your 'stuck at 2' cause.")
        print("        Fix: polyctl settings set irradiance_prescaler 0.75\n")
        return
    if max_val <= min_val:
        print("   [!!] irradiance_max <= irradiance_min  ->  the normalization")
        print("        collapses (or divides by zero) and the curve is unusable.")
        print("        Fix: set irradiance_min ~1.8 and irradiance_max ~5.2\n")
        return

    # The two physically meaningful break-points of the curve.
    floor_irr = math.exp(min_val / pre_scale) - 1   # below this -> value 2
    full_irr = math.exp(max_val / pre_scale) - 1     # at/above this -> value 50
    print(f"   -> device value stays at the floor (2) for ALL irradiance "
          f"<= {floor_irr:.1f} W/m^2")
    print(f"   -> device value reaches full (50) only at irradiance "
          f">= {full_irr:.0f} W/m^2")
    print( "      (reference: clear-sky noon GHI peaks ~1000 W/m^2; the solar")
    print( "       constant above the atmosphere is 1361 W/m^2)\n")

    print("   irr(W/m^2)  perceived  normalized  device")
    for irr in (0, 5, 10, 25, 50, 100, 200, 400, 600, 800, 1000):
        perceived, n = normalize(irr, min_val, max_val, pre_scale)
        dv = device_value(n, gamma)
        print(f"   {irr:>8}    {perceived:8.3f}   {n:8.3f}   {dv:6.1f}"
              f"  (int {int(max(0, min(50, dv)))})")

    if floor_irr > 50:
        print(f"\n   [!] irradiance_min is high: anything below {floor_irr:.0f} W/m^2")
        print("       floors to 2, so dim/overcast daylight reads as 'off'.")
    if full_irr > 1361:
        print("\n   [!] max_val is set so high that FULL brightness is physically")
        print("       unreachable — the keyboard tops out well below 50 even in")
        print("       direct noon sun. The usable range is compressed.")
    print()


def live_paths(s, min_val, max_val, pre_scale, gamma=1.0):
    print("=" * 72)
    print("2. LIVE — what each irradiance source returns right now")
    print("=" * 72)
    now = datetime.now()
    print(f"   host local time : {now.isoformat(timespec='seconds')}  "
          f"(tz offset {now.astimezone().strftime('%z') or 'naive'})")
    print(f"   online location lookup allowed : {s.location_lookup}")
    print(f"   online irradiance lookup allowed: {s.online_lookup}\n")

    s.init_location()
    if not s.location_known:
        print("   [!] location UNKNOWN (IP geolocation failed / disabled).")
        print("       get_irradiance_now() returns the crude hour-of-day fallback:")
        irr = min(19 - 7, max(0, now.hour - 7)) / 12
        _report_value("hour-of-day fallback", irr, min_val, max_val, pre_scale, gamma)
        return
    print(f"   location: lat {s.latitude:.4f}  lon {s.longitude:.4f}")
    print("   irradiance source: online open-meteo (cloud-aware) with a pure-math\n"
          "   clear-sky fallback (Haurwitz model) when offline / lookup disabled.\n")

    # (a) The actual call the firmware-facing code makes.
    try:
        irr = s.get_irradiance_now()
        _report_value("get_irradiance_now() [the value actually used]", irr,
                      min_val, max_val, pre_scale, gamma)
    except Exception as e:
        print(f"   get_irradiance_now() raised {type(e).__name__}: {e}")
        print("   (the worker periodic swallows this -> brightness is NOT updated)\n")

    # (b) Show the pure-math clear-sky fallback over the day, so a "stuck at 2"
    #     can be traced to e.g. night-time / sun-below-horizon.
    _clearsky_probe(s)


def _report_value(label, irr, min_val, max_val, pre_scale, gamma=1.0):
    _perceived, n = normalize(irr, min_val, max_val, pre_scale)
    dv = device_value(n, gamma)
    print(f"   {label}")
    print(f"      irradiance = {irr:.2f} W/m^2  -> device value "
          f"{dv:.1f} (int {int(max(0, min(50, dv)))})")
    if dv <= 2.5:
        if pre_scale > 0:
            floor_irr = math.exp(min_val / pre_scale) - 1
            print("      => this is the FLOOR (2). Cause: irradiance read as "
                  f"<= {floor_irr:.1f} W/m^2.\n")
        else:
            # The tool exists to explain degenerate configs; a 0/negative
            # prescaler pins normalization at the floor, so don't divide by it.
            print("      => this is the FLOOR (2). Cause: irradiance_prescaler "
                  "<= 0 pins normalization at the minimum.\n")
    else:
        print()


def _clearsky_probe(s):
    """Print the pure-math clear-sky GHI across today (UTC-driven, so it's
    timezone-correct by construction) and flag night-time, which is the usual
    legitimate 'stuck at 2' cause on the offline path."""
    print("   clear-sky model probe (offline fallback path):")
    print("   Haurwitz GHI = 1098 * cos(Z) * exp(-0.059/cos(Z)), Z from solar")
    print("   declination + hour angle. Cloudless by nature (offline can't know")
    print("   clouds); the online open-meteo value above already reflects them.\n")

    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    ghis = [(h, s._clearsky_ghi(midnight + timedelta(hours=h))) for h in range(24)]
    peak_h, peak_ghi = max(ghis, key=lambda hg: hg[1])
    cur_ghi = s._clearsky_ghi(now)
    print(f"   solar peak : ~{peak_h:02d}:00 UTC ({peak_ghi:.0f} W/m^2)")
    print(f"   GHI now    : {cur_ghi:.1f} W/m^2  ({now.strftime('%H:%M')} UTC)")
    if cur_ghi < 10:
        print("   [!] sun is at/below the horizon now -> clear-sky GHI ~0, so the")
        print("       offline fallback floors brightness to 2. Expected at night.")
    print()


def main():
    settings = PolySettings()
    min_val = settings.get("irradiance_min")
    max_val = settings.get("irradiance_max")
    pre_scale = settings.get("irradiance_prescaler")
    gamma = settings.get("brightness_gamma")

    print("\nPolyKybd daylight-brightness diagnostics\n")
    if not settings.get("brightness_set_daylight_dependent"):
        print("[note] brightness_set_daylight_dependent is OFF — the periodic does "
              "nothing; the keyboard keeps whatever brightness was last set.\n")

    curve_analysis(min_val, max_val, pre_scale, gamma)

    s = Sunlight(settings.get("brightness_allow_online_location_lookup"),
                 settings.get("brightness_allow_online_irradiance_request"))
    live_paths(s, min_val, max_val, pre_scale, gamma)


if __name__ == "__main__":
    main()
