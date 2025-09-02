from polyhost.util.math_util import find_nearest, natural_divisors


class DeviceSettings:
    """All settings that are defined by the keyboard, not by software"""
    _vid = 0x2021
    _pid = 0x2007

    _hid_report_size_in_bytes = 32
    _hid_console_report_size_in_bytes = 64
    _via_command_bytes = 1
    _polykybd_command_bytes = 1
    _max_payload_bytes_per_report = _hid_report_size_in_bytes - _via_command_bytes - _polykybd_command_bytes

    _overlay_command_bytes_plain_per_report = 3
    _overlay_command_bytes_compressed_once = 2 # 1 byte for the keycode and 1 for the modifier
    _overlay_command_bytes_roi_once = 5 # 1 for keycode, 4 for modifier|top|bottom|left|right|compressed

    _overlay_resolution_x = 72
    _overlay_resolution_y = 40

    # pack 8 pixel bits into a single byte
    _overlay_plain_data_bytes_total = int(_overlay_resolution_x * _overlay_resolution_y) / 8

    # 24 bytes in case of 32 byte reports
    _overlay_plain_data_bytes_per_report = find_nearest(_max_payload_bytes_per_report, natural_divisors(_overlay_plain_data_bytes_total))

    # 360 bytes / 24 bytes = 15 reports
    _overlay_plain_data_report_count = int(_overlay_plain_data_bytes_total / _overlay_plain_data_bytes_per_report)

    # the mapping indices are 10 bits wide
    _overlay_mapping_indices_per_report = int( _max_payload_bytes_per_report * 8 ) / 10

    _hid_raw_usage_page         = 0xFF60
    _hid_raw_usage              = 0x61

    _hid_console_usage_page    = 0xFF31
    _hid_console_usage         = 0x74

    @property
    def VID(self):
        """Vendor ID"""
        return self._vid

    @property
    def PID(self):
        """Product ID"""
        return self._pid

    @property
    def OVERLAY_RES_X(self):
        return self._overlay_resolution_x

    @property
    def OVERLAY_RES_Y(self):
        return self._overlay_resolution_y

    @property
    def HID_REPORT_SIZE(self):
        return self._hid_report_size_in_bytes

    @property
    def HID_CONSOLE_REPORT_SIZE(self):
        return self._hid_console_report_size_in_bytes

    @property
    def MAX_PAYLOAD_BYTES_PER_REPORT(self):
        return self._max_payload_bytes_per_report

    @property
    def OVERLAY_CMD_BYTES_PER_PLAIN_REPORT(self):
        return self._overlay_command_bytes_plain_per_report

    @property
    def OVERLAY_CMD_BYTES_COMPRESSED_ONCE(self):
        return self._overlay_command_bytes_compressed_once

    @property
    def OVERLAY_CMD_BYTES_ROI_ONCE(self):
        return self._overlay_command_bytes_roi_once

    @property
    def OVERLAY_PLAIN_DATA_BYTES_TOTAL(self):
        return self._overlay_plain_data_bytes_total

    @property
    def OVERLAY_PLAIN_DATA_BYTES_PER_REPORT(self):
        return self._overlay_plain_data_bytes_per_report

    @property
    def OVERLAY_PLAIN_DATA_REPORT_COUNT(self):
        return self._overlay_plain_data_report_count

    @property
    def OVERLAY_MAPPING_INDICES_PER_REPORT(self):
        return self._overlay_mapping_indices_per_report

    @property
    def HID_RAW_USAGE_PAGE(self):
        return self._hid_raw_usage_page

    @property
    def HID_RAW_USAGE(self):
        return self._hid_raw_usage

    @property
    def HID_CONSOLE_USAGE_PAGE(self):
        return self._hid_console_usage_page

    @property
    def HID_CONSOLE_USAGE(self):
        return self._hid_console_usage
