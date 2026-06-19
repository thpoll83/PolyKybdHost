import logging
from datetime import datetime, timezone, timedelta
import math

# Lightweight by design: the only external dependency is `requests` (imported
# lazily inside the lookup methods, which run on the HID worker thread, never on
# the startup path). The previous implementation pulled pvlib + pandas + scipy
# (for an offline clear-sky model) and geocoder + pytz — a heavy scientific
# stack whose cold import cost seconds on Windows. Clouds only ever come from
# the online open-meteo value anyway; pvlib's get_clearsky was a *clear-sky*
# (cloudless) fallback, so a pure-math clear-sky estimate is equivalent there.


class Sunlight:
    def __init__(self, allow_location_lookup, allow_online_lookup):
        self.longitude = None
        self.latitude = None
        self.log = logging.getLogger('PolyHost')
        self.online_lookup = allow_online_lookup
        self.location_lookup = allow_location_lookup
        self.location_known = False

    def init_location(self):
        if self.location_lookup and not self.location_known:
            try:
                import requests
                # Free, no-key IP geolocation. HTTP only on the free tier, which
                # is fine — coarse city-level location is not sensitive and it's
                # cached for the process once resolved (location_known).
                resp = requests.get("http://ip-api.com/json", timeout=5)
                data = resp.json()
                if data.get("status") == "success":
                    self.latitude = float(data["lat"])
                    self.longitude = float(data["lon"])
                    self.location_known = True
                    self.log.info("Location lat %f long %f (%s)",
                                  self.latitude, self.longitude,
                                  data.get("timezone", "?"))
                else:
                    self.log.warning("IP geolocation returned no fix: %s",
                                     data.get("message", data))
            except Exception as e:
                self.log.warning(
                    "Failed to query location (%s), maybe due to missing "
                    "internet connection.", e)

    def get_irradiance_now(self):
        self.init_location()

        if self.location_known:
            if self.online_lookup:
                irr = self._online_irradiance()
                if irr is not None:
                    return irr
                self.log.info("Using location/time clear-sky model instead.")

            # Clear-sky fallback (offline or online lookup failed). Cloudless by
            # nature — same as the old pvlib path, just pure math (see
            # _clearsky_ghi). Driven by the absolute UTC instant so the sun is
            # placed correctly regardless of the host's timezone.
            ghi = self._clearsky_ghi()
            self.log.debug("Clear-sky irradiance value: %f", ghi)
            return ghi

        # No location at all: crude hour-of-day shape (0 at 07:00, ramp to 19:00).
        return min(19 - 7, max(0, datetime.now().hour - 7)) / 12

    def _online_irradiance(self):
        """open-meteo shortwave_radiation for the current hour (W/m^2), which
        DOES reflect clouds. Returns the value, or None on any failure so the
        caller falls back to the clear-sky model. Best-effort with a bounded
        timeout — it runs on the HID worker thread's 10-min periodic."""
        import requests
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={self.latitude}&longitude={self.longitude}"
            f"&hourly=shortwave_radiation"
            f"&timezone=auto"
        )
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            times = data['hourly']['time']
            radiation = data['hourly']['shortwave_radiation']

            # open-meteo's time table is local-to-location (timezone=auto). It
            # also hands us utc_offset_seconds, so we derive "now" in the
            # location's local time from UTC with a plain offset — no timezone
            # database (pytz/zoneinfo/tzdata) needed. Deriving "now" from the
            # host clock would break whenever the host tz differs from location.
            offset = data.get("utc_offset_seconds", 0)
            loc_now = datetime.now(timezone.utc) + timedelta(seconds=offset)
            today = loc_now.date().isoformat()
            hour_now = loc_now.hour

            for idx, timestamp in enumerate(times):
                if timestamp.startswith(today) and int(timestamp[11:13]) == hour_now:
                    self.log.debug("Timestamp for irradiance data[%d]: %s", idx, timestamp)
                    # open-meteo can emit null for individual hours; treat a null
                    # current hour as 0 and a null next hour as a repeat.
                    cur = radiation[idx]
                    cur = 0.0 if cur is None else cur
                    nxt = radiation[idx + 1] if len(radiation) > (idx + 1) else cur
                    nxt = cur if nxt is None else nxt
                    return (cur + nxt) / 2

            self.log.warning("Found no matching entry in time table from api.open-meteo.com: %s", times)
        except Exception as e:
            self.log.warning(
                "Online irradiance lookup failed (%s: %s).", type(e).__name__, e)
        return None

    def _clearsky_ghi(self, when_utc=None):
        """Rough clear-sky global horizontal irradiance (W/m^2) from solar
        geometry alone — no clouds (the offline fallback case). Uses the
        Haurwitz model GHI = 1098 * cos(Z) * exp(-0.059 / cos(Z)), where the
        solar zenith Z comes from a standard declination + hour-angle solar
        position. Accurate enough for driving the brightness curve (the value is
        squashed by log + clamp downstream); it intentionally omits the
        equation of time (<~15 min) and atmospheric refraction."""
        now = when_utc or datetime.now(timezone.utc)
        day_of_year = now.timetuple().tm_yday
        # Solar declination (Cooper's equation), radians.
        decl = math.radians(23.45) * math.sin(2 * math.pi * (284 + day_of_year) / 365.0)
        lat = math.radians(self.latitude)
        # Solar time ~ UTC shifted by longitude (15 deg/hour); solar noon -> 0.
        utc_hours = now.hour + now.minute / 60.0 + now.second / 3600.0
        solar_time = utc_hours + self.longitude / 15.0
        hour_angle = math.radians(15.0 * (solar_time - 12.0))
        cos_zenith = (math.sin(lat) * math.sin(decl)
                      + math.cos(lat) * math.cos(decl) * math.cos(hour_angle))
        if cos_zenith <= 0.0:          # sun below the horizon
            return 0.0
        return 1098.0 * cos_zenith * math.exp(-0.059 / cos_zenith)

    def get_brightness_now(self, min_val=1.8, max_val=6.5, pre_scale = 0.75):
        irradiance = self.get_irradiance_now()
        perceived_brightness = math.log(1+irradiance)*pre_scale
        span = max_val - min_val
        if span <= 0:
            # Degenerate config (max <= min) — would divide by zero. Warn and
            # treat as "no usable range" rather than crashing the periodic.
            self.log.warning(
                "irradiance_max (%s) <= irradiance_min (%s): brightness range is "
                "empty; defaulting to minimum. Check your brightness settings.",
                max_val, min_val)
            return 0.0
        normalized = (max(min_val, min(max_val, perceived_brightness)) - min_val) / span
        self.log.info(
            "Normalized brightness value: %f, perceived: %f (irradiance %f)",
            normalized,
            perceived_brightness,
            irradiance,
        )
        return normalized

    def allow_online_lookup(self, allow_online_lookup):
        self.online_lookup = allow_online_lookup

    def allow_location_lookup(self, allow_location_lookup):
        self.location_lookup = allow_location_lookup
