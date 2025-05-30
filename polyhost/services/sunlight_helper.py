import logging
from datetime import datetime, timezone
import math

import requests
from pvlib.location import Location
import pandas as pd
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
                self.location = geocoder.ip('me')
                self.latitude, self.longitude = self.location.latlng

                # Create location object
                self.site = Location(self.latitude, self.longitude)

                self.log.info("Location lat %f long %f", self.latitude, self.longitude)
                self.location_known = True
            except:
                self.log.warning("Failed to query location, maybe due to missing internet connection.")

    def get_irradiance_now(self):
        self.init_location()

        if self.location_known:
            if self.online_lookup:
                now_utc = datetime.now(timezone.utc)
                today = now_utc.date().isoformat()
                hour_now = now_utc.hour

                # Step 3: Query Open-Meteo hourly solar radiation
                url = (
                    f"https://api.open-meteo.com/v1/forecast?"
                    f"latitude={self.latitude}&longitude={self.longitude}"
                    f"&hourly=shortwave_radiation"
                    f"&timezone=auto"
                )

                response = requests.get(url)
                data = response.json()

                # Step 4: Extract current hour's solar radiation
                times = data['hourly']['time']
                radiation = data['hourly']['shortwave_radiation']

                # Find index for current hour
                for idx, timestamp in enumerate(times):
                    if timestamp.startswith(today) and int(timestamp[11:13]) == hour_now:
                        self.log.debug("Timestamp for irradiance data[%d]: %s", idx, timestamp)
                        return (radiation[idx] + (radiation[idx+1] if len(radiation)>(idx+1) else radiation[idx]))/2

                self.log.warning("Found no matching entry in time table from api.open-meteo.com: %s", times)
                self.log.info("Using location and time based approach instead.")

            # Define current time in UTC
            pd_now = pd.Timestamp.utcnow()
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