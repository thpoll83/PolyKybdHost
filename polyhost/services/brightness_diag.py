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
from datetime import datetime, date, timedelta

from polyhost.settings import PolySettings
from polyhost.services.sunlight_helper import Sunlight


def device_value(normalized):
    """The mapping PolyCore applies: normalized 0..1 -> device 2..50."""
    return 2 + normalized * 48


def normalize(irradiance, min_val, max_val, pre_scale):
    """Mirror of Sunlight.get_brightness_now's normalization (no logging)."""
    perceived = math.log(1 + irradiance) * pre_scale
    normalized = (max(min_val, min(max_val, perceived)) - min_val) / (max_val - min_val)
    return perceived, normalized


def curve_analysis(min_val, max_val, pre_scale):
    print("=" * 72)
    print("1. CALIBRATION — irradiance -> device brightness curve")
    print("=" * 72)
    print(f"   settings: irradiance_min={min_val}  irradiance_max={max_val}  "
          f"prescaler={pre_scale}")
    print(f"   formula : perceived = ln(1+irr) * {pre_scale}")
    print( "             normalized = clamp(perceived, min, max) mapped to 0..1")
    print( "             device    = 2 + normalized * 48   (then int-clipped 0..50)\n")

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
        print(f"   {irr:>8}    {perceived:8.3f}   {n:8.3f}   {device_value(n):6.1f}"
              f"  (int {int(max(0, min(50, device_value(n))))})")

    if full_irr > 1361:
        print("\n   [!] max_val is set so high that FULL brightness is physically")
        print("       unreachable — the keyboard tops out well below 50 even in")
        print("       direct noon sun. The usable range is compressed.")
    print()


def live_paths(s, min_val, max_val, pre_scale):
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
        _report_value("hour-of-day fallback", irr, min_val, max_val, pre_scale)
        return
    print(f"   location: lat {s.latitude:.4f}  lon {s.longitude:.4f}")
    print(f"   pvlib Location.tz = {getattr(s.site, 'tz', '?')!r} "
          "(constructed without a tz -> defaults to 'UTC')\n")

    # (a) The actual call the firmware-facing code makes.
    try:
        irr = s.get_irradiance_now()
        _report_value("get_irradiance_now() [the value actually used]", irr,
                      min_val, max_val, pre_scale)
    except Exception as e:
        print(f"   get_irradiance_now() raised {type(e).__name__}: {e}")
        print("   (the worker periodic swallows this -> brightness is NOT updated)\n")

    # (b) Clear-sky path the way the code does it (naive local time) vs the
    #     timezone-correct way — this exposes the tz bug.
    _clearsky_timezone_probe(s)


def _report_value(label, irr, min_val, max_val, pre_scale):
    perceived, n = normalize(irr, min_val, max_val, pre_scale)
    print(f"   {label}")
    print(f"      irradiance = {irr:.2f} W/m^2  -> device value "
          f"{device_value(n):.1f} (int {int(max(0, min(50, device_value(n))))})")
    if device_value(n) <= 2.5:
        print("      => this is the FLOOR (2). Cause: irradiance read as "
              f"<= {math.exp(min_val/pre_scale)-1:.1f} W/m^2.\n")
    else:
        print()


def _clearsky_timezone_probe(s):
    """Show the modelled clear-sky GHI across today, the buggy (naive-local,
    treated-as-UTC) way and the timezone-correct way, so the offset is visible."""
    try:
        import pandas as pd
        from pvlib.location import Location
    except Exception as e:
        print(f"   (skipping clear-sky timezone probe: {e})")
        return

    print("   clear-sky timezone probe (fallback path):")
    print("   The code calls Location(lat, lon).get_clearsky(pd.Timestamp.now()).")
    print("   pd.Timestamp.now() is timezone-NAIVE host-local time, and the")
    print("   Location was built with no tz (default 'UTC'), so pvlib models the")
    print("   sun as if your wall clock were UTC. If you are far from UTC in")
    print("   longitude that puts the modelled sun hours away from reality.\n")

    today = date.today()
    hours = pd.date_range(datetime(today.year, today.month, today.day),
                          periods=24, freq="h")

    # Buggy: naive local time, Location default tz='UTC'.
    site_utc = Location(s.latitude, s.longitude)
    ghi_buggy = site_utc.get_clearsky(hours)["ghi"]

    # Correct: localize the times to the location's own timezone.
    try:
        from timezonefinder import TimezoneFinder
        tz = TimezoneFinder().timezone_at(lat=s.latitude, lng=s.longitude)
    except Exception:
        tz = None
    correct_line = ""
    if tz:
        site_local = Location(s.latitude, s.longitude, tz=tz)
        local_hours = hours.tz_localize(tz)
        ghi_correct = site_local.get_clearsky(local_hours)["ghi"].values
        peak_correct = int(local_hours[ghi_correct.argmax()].hour)
        correct_line = (f"   tz-correct ({tz}): modelled solar peak at "
                        f"~{peak_correct:02d}:00 local")

    peak_buggy = int(hours[ghi_buggy.values.argmax()].hour)
    print(f"   as-coded (naive->UTC): modelled solar peak at ~{peak_buggy:02d}:00 "
          "of your wall clock")
    if correct_line:
        print(correct_line)
    cur = int(datetime.now().hour)
    print(f"   modelled GHI at your current hour ({cur:02d}:00) via the as-coded "
          f"path: {ghi_buggy.values[cur]:.1f} W/m^2")
    if correct_line and ghi_buggy.values[cur] < 10 <= max(ghi_correct):
        print("   [!] the as-coded path reads ~0 now while the tz-correct model has "
              "real daylight\n       -> THIS is the 'stuck at 2' cause on this path.")
    print()


def main():
    settings = PolySettings()
    min_val = settings.get("irradiance_min")
    max_val = settings.get("irradiance_max")
    pre_scale = settings.get("irradiance_prescaler")

    print("\nPolyKybd daylight-brightness diagnostics\n")
    if not settings.get("brightness_set_daylight_dependent"):
        print("[note] brightness_set_daylight_dependent is OFF — the periodic does "
              "nothing; the keyboard keeps whatever brightness was last set.\n")

    curve_analysis(min_val, max_val, pre_scale)

    s = Sunlight(settings.get("brightness_allow_online_location_lookup"),
                 settings.get("brightness_allow_online_irradiance_request"))
    live_paths(s, min_val, max_val, pre_scale)


if __name__ == "__main__":
    main()
