import threading
import platform
if platform.system() == 'Windows':
    import ctypes
    import os 
    ctypes.CDLL(os.path.dirname(os.path.realpath(__file__)) + '\\win-hidapi-0-14\\hidapi.dll')
import hid

usage_page    = 0xFF60
usage         = 0x61
report_length = 32

class HidHelper:
    def __del__(self):
        if self.interface:
            self.interface.close()

    def __init__(self, vid, pid):
        self.pid = pid
        self.vid = vid
        self.lock = threading.Lock()

        device_interfaces = hid.enumerate(vid, pid)
        raw_hid_interfaces = [i for i in device_interfaces if i['usage_page'] == usage_page and i['usage'] == usage]

        if len(raw_hid_interfaces) != 0:
            self.interface = hid.Device(path=raw_hid_interfaces[0]['path'])
        else:
            self.interface = None

    def interface_aquired(self):
        return self.interface != None

    def send(self, data):

        if self.interface is None:
            return False, "No Interface"

        request_data = [0x00] * (report_length + 1) # First byte is Report ID
        request_data[1:len(data) + 1] = data
        request_report = bytes(request_data)

        try:
            with self.lock:
                result = self.interface.write(request_report)
        except Exception as e:
            return False, f"Exception: {e}"

        return True, result

    def send_multiple(self, data, received_lock):
        if self.interface is None:
            return False, "No Interface", received_lock

        request_data = [0x00] * (report_length + 1) # First byte is Report ID
        request_data[1:len(data) + 1] = data
        request_report = bytes(request_data)

        try:
            if received_lock is None:
                self.lock.acquire()
            elif received_lock != self.lock:
                return False, "Lock missmatch", received_lock
            result = self.interface.write(request_report)
        except Exception as e:
            self.lock.release()
            return False, f"Exception: {e}"

        return True, result, self.lock

    def read(self, timeout):
        if self.interface is None:
            return False, "No Interface"

        try:
            with self.lock:
                response_report = self.interface.read(report_length, timeout=timeout)
        except Exception as e:
            return False, f"Exception: {e}"

        return True, response_report.decode().strip('\x00')

    def send_and_read(self, data, timeout):
        if self.interface is None:
            return False, "No Interface"

        request_data = [0x00] * (report_length + 1) # First byte is Report ID
        request_data[1:len(data) + 1] = data
        request_report = bytes(request_data)

        try:
            with self.lock:
                self.interface.write(request_report)
                response_report = self.interface.read(report_length, timeout=timeout)
        except Exception as e:
            return False, f"Exception: {e}"

        return True, response_report.decode().strip('\x00')
