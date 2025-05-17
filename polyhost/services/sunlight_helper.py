import logging
from datetime import datetime, timezone

import requests
from pvlib.location import Location
import pandas as pd
import geocoder

class Sunlight:
    def __init__(self, allow_online_lookup):
        self.site = None
        self.longitude = None
        self.latitude = None
        self.location = None
        self.log = logging.getLogger('PolyHost')
        self.online_lookup = allow_online_lookup
        self.location_known = False

    def init_location(self):
        if not self.location_known:
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
                        return radiation[idx]

                self.log.warning("Found no matching entry in time table from api.open-meteo.com: %s", times)
                self.log.info("Using location and time based approach instead.")

            # Define current time in UTC
            pd_now = pd.Timestamp.utcnow()
            times = pd.DatetimeIndex([pd_now])

            clear_sky = self.site.get_clearsky(times)  # GHI, DNI, DHI values (in W/m^2)
            if len(clear_sky['ghi'].values) > 0:
                return clear_sky['ghi'].values[0]

            self.log.warning("Location based calculation failed")

        return min(19-7, max(0, datetime.now().hour - 7))/12

    def get_brightness_now(self, min_val=50, max_val=900):
        irradiance = self.get_irradiance_now()
        normalized = (irradiance - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, normalized))

    def allow_online_lookup(self, allow_online_lookup):
        self.online_lookup = allow_online_lookup

