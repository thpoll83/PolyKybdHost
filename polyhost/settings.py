import logging
import os

import yaml
from platformdirs import user_config_dir

class PolySettings:
    """ Stores program specific settings """
    def __init__(self):
        self.collection = None
        self.log = logging.getLogger('PolyHost')
        self.APP_NAME = "PolyHost"
        self.CONFIG_FILENAME = "settings.yaml"

        # Get the user-specific config directory
        directory = user_config_dir(self.APP_NAME)
        self.path = os.path.join(directory, self.CONFIG_FILENAME)

        # Ensure config directory exists
        os.makedirs(directory, exist_ok=True)

        # Default settings
        self.defaults = {
            "unicode_send_composition_mode": True,
            "brightness_set_daylight_dependent": True,
            "brightness_allow_online_irradiance_request": True,
            "brightness_allow_online_location_lookup": True,
            "irradiance_min": 1.8,
            "irradiance_max": 6.5,
            "irradiance_prescaler": 0.75,
            "debug_window_detection_if_not_connected_to_poly_kybd": False
        }

        # Load settings
        if os.path.exists(self.path):
            self.load()
        else:
            self.collection = self.defaults
        self.save()

        self.log.info("\nCurrent settings:\n====================================\n%s", yaml.dump(
            self.collection, default_flow_style=False))

    def get(self, name):
        return self.collection[name]

    def get_all(self):
        return self.collection

    def set_all(self, new_settings):
        self.collection = new_settings
        self.save()

    def load(self):
        with open(self.path, encoding='utf-8') as f:
            self.collection = yaml.safe_load(f) or {}
        for key, value in self.defaults.items():
            self.collection.setdefault(key, value)

        self.collection = {k: v for k, v in self.collection.items() if k in self.defaults}

    def restore_defaults(self):
        self.collection = self.defaults
        self.save()

    def save(self):
        with open(self.path, "w", encoding='utf-8') as f:
            yaml.safe_dump(self.collection, f)
        self.log.info("Saved settings to %s", self.path)

