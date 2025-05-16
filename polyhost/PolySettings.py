import logging
import os

import yaml
from platformdirs import user_config_dir

class PolySettings:
    def __init__(self):
        self.log = logging.getLogger('PolyHost')
        self.APP_NAME = "PolyHost"
        self.CONFIG_FILENAME = "settings.yaml"

        # Get the user-specific config directory
        config_dir = user_config_dir(self.APP_NAME)
        config_path = os.path.join(config_dir, self.CONFIG_FILENAME)

        # Ensure config directory exists
        os.makedirs(config_dir, exist_ok=True)

        # Default settings
        default_settings = {
            "send_unicode_mode_to_kb": True,
            "send_daylight_dependent_brightness": True,
            "allow_online_request_for_brightness": True
        }

        # Load settings
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                self.settings = yaml.safe_load(f) or {}
            for key, value in default_settings.items():
                self.settings.setdefault(key, value)
        else:
            self.settings = default_settings
            with open(config_path, "w") as f:
                yaml.safe_dump(self.settings, f)

        self.log.info("Current settings:\n%s", str(self.settings))

    def get(self):
        return self.settings
