import logging
from datetime import datetime
import math

import requests
from pvlib.location import Location
import pandas as pd
import pytz
import geocoder

class Sunlight:
    def __init__(self, allow_location_lookup, allow_online_lookup):
        self.site = None
        self.longitude = None
        self.latitude = None
        self.location = None
        self.log = logging.getLogger('PolyHost')
        self.online_lookup = allow_online_lookup
        self.location_lookup = allow_location_lookup
        self.location_known = False

    def init_location(self):
        if self.location_lookup and not self.location_known:
            try:
                self.location = geocoder.ip('me', timeout=5.0)
                self.latitude, self.longitude = self.location.latlng

                # Create location object. tz='UTC' is deliberate: clear-sky
                # solar position is driven by the absolute UTC instant we pass
                # in (see get_irradiance_now), not by the civil timezone — so
                # we keep the model in UTC and feed it tz-aware UTC timestamps.
                self.site = Location(self.latitude, self.longitude, tz='UTC')

                self.log.info("Location lat %f long %f", self.latitude, self.longitude)
                self.location_known = True
            except:
                self.log.warning("Failed to query location, maybe due to missing internet connection.")

    def get_irradiance_now(self):
        self.init_location()

        if self.location_known:
            if self.online_lookup:
                # Step 3: Query Open-Meteo hourly solar radiation
                url = (
                    f"https://api.open-meteo.com/v1/forecast?"
                    f"latitude={self.latitude}&longitude={self.longitude}"
                    f"&hourly=shortwave_radiation"
                    f"&timezone=auto"
                )

                # The whole online lookup is best-effort: any failure (network,
                # bad JSON, missing fields) logs and falls through to the
                # location/time clear-sky model below rather than propagating.
                # Bounded timeout: this runs on the HID worker thread (10-min
                # brightness periodic) — without it a stalled connection wedges
                # that thread's periodic schedule.
                try:
                    response = requests.get(url, timeout=10)
                    data = response.json()

                    # Step 4: Extract current hour's solar radiation
                    times = data['hourly']['time']
                    radiation = data['hourly']['shortwave_radiation']

                    # Match the current hour in the LOCATION's timezone (the
                    # time table uses timezone=auto, i.e. local-to-location).
                    # Deriving "now" from the host clock breaks whenever the
                    # host's timezone differs from the keyboard's location.
                    tz_name = data.get('timezone')
                    try:
                        loc_now = (datetime.now(pytz.utc).astimezone(pytz.timezone(tz_name))
                                   if tz_name else datetime.now())
                    except Exception:
                        loc_now = datetime.now()
                    today = loc_now.date().isoformat()
                    hour_now = loc_now.hour

                    # Find index for current hour
                    for idx, timestamp in enumerate(times):
                        if timestamp.startswith(today) and int(timestamp[11:13]) == hour_now:
                            self.log.debug("Timestamp for irradiance data[%d]: %s", idx, timestamp)
                            # open-meteo can emit null for individual hours;
                            # treat a null current hour as 0 and a null next
                            # hour as a repeat of the current one.
                            cur = radiation[idx]
                            cur = 0.0 if cur is None else cur
                            nxt = radiation[idx + 1] if len(radiation) > (idx + 1) else cur
                            nxt = cur if nxt is None else nxt
                            return (cur + nxt) / 2

                    self.log.warning("Found no matching entry in time table from api.open-meteo.com: %s", times)
                    self.log.info("Using location and time based approach instead.")
                except Exception as e:
                    self.log.warning(
                        "Online irradiance lookup failed (%s: %s); using location/time model instead.",
                        type(e).__name__, e)

            # Fall back to the clear-sky model. Use the absolute UTC instant
            # (tz-aware) so pvlib places the sun correctly regardless of the
            # host's timezone — a naive Timestamp.now() was treated as UTC by
            # pvlib, shifting the modelled sun by the user's UTC offset and
            # reading ~0 W/m^2 (-> minimum brightness) during real daylight.
            pd_now = pd.Timestamp.now(tz=pytz.utc)
            times = pd.DatetimeIndex([pd_now])

            clear_sky = self.site.get_clearsky(times)  # GHI, DNI, DHI values (in W/m^2)
            if len(clear_sky['ghi'].values) > 0:
                self.log.debug("Irradiance value: %f", clear_sky['ghi'].values[0])
                return clear_sky['ghi'].values[0]

            self.log.warning("Location based calculation failed")

        return min(19-7, max(0, datetime.now().hour - 7))/12

    def get_brightness_now(self, min_val=1.8, max_val=6.5, pre_scale = 0.75):
        irradiance = self.get_irradiance_now()
        perceived_brightness = math.log(1+irradiance)*pre_scale
        normalized = (max(min_val, min(max_val, perceived_brightness)) - min_val) / (max_val - min_val)
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