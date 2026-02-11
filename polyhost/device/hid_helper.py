import pathlib
import threading
import platform
import os
from typing import Any
if platform.system() == 'Windows':
    import ctypes
    ctypes.CDLL(os.path.dirname(os.path.realpath(__file__)) + '\\win-hidapi-0-15\\hidapi.dll')
try:
    import hid
except ImportError:
    print("""Library hidapi missing. Please Install:

    Arch Linux
    ==========
    Binary distributions are available in the community repository.

    Enable the community repository in /etc/pacman.conf
    [community]
    Include = /etc/pacman.d/mirrorlist
    Install hidapi
    pacman -Sy hidapi
  
    CentOS/RHEL
    ===========
    Binary distributions are available through EPEL.

    yum install hidapi

    Fedora
    ======
    Binary distributions are available.

    dnf install hidapi

    Ubuntu/Debian
    =============
    Binary distributions are available.

    apt install libhidapi-hidraw0
    or

    apt install libhidapi-libusb0

    Others
    ======
    Binary distributions may be available in your package repositories.
    If not, you can build from source as described in the libusb/hidapi README.

    Windows
    =======
    Installation procedure for Windows is described in the libusb/hidapi README.

    Binary distributions are provided by libusb/hidapi

    OSX
    ===
    There are currently no official binary distributions for Mac,
    so you must build hidapi yourself.

    Installation instructions are described in the libusb/hidapi README.

    You can also use brew:

    brew install hidapi

    FreeBSD
    =======
    Binary distributions are available.

    pkg install -g 'py3*-hid'
    """)
    raise

PERMISSION_MSG = f"""It looks like you do not have permission to access the device.
Please run the following commands, then reconnect the device and restart the application:

sudo cp {os.path.join(pathlib.Path(__file__).parent.resolve(), "99-hid.rules")} /etc/udev/rules.d
sudo udevadm control --reload-rules
sudo udevadm trigger
"""

class HidHelper:
    def __del__(self):
        if self.interface:
            self.interface.close()

    def __init__(self, settings):
        self.settings = settings
        self.lock = threading.Lock()

        device_interfaces = hid.enumerate(self.settings.VID, self.settings.PID)
        raw_hid_interfaces = [i for i in device_interfaces if i['usage_page'] == self.settings.HID_RAW_USAGE_PAGE and i['usage'] == self.settings.HID_RAW_USAGE]

        if len(raw_hid_interfaces) != 0:
            try:
                self.interface = hid.Device(path=raw_hid_interfaces[0]['path'])
            except hid.HIDException as e:
                print(PERMISSION_MSG)
                raise e
                
        else:
            self.interface = None

        console_hid_interfaces = [j for j in device_interfaces if j['usage_page'] == self.settings.HID_CONSOLE_USAGE_PAGE and j['usage'] == self.settings.HID_CONSOLE_USAGE]
                                                                    
        if len(console_hid_interfaces) != 0:
            try:
                self.remote_console = hid.Device(path=console_hid_interfaces[0]['path'])
            except hid.HIDException as e:
                print(PERMISSION_MSG)
                raise e
                
        else:
            self.remote_console = None

    def get_console_output(self):
        return self.remote_console.read(self.settings.HID_CONSOLE_REPORT_SIZE, timeout=0)

    def interface_acquired(self):
        return self.interface is not None

    def __send(self, data: bytearray) -> tuple[bool, Any]:
        """ Write a data report without reading the response"""

        if self.interface is None:
            return False, "No Interface"

        request_data = [0x00] * (self.settings.HID_REPORT_SIZE + 1) # First byte is Report ID
        request_data[1:len(data) + 1] = data
        request_report = bytes(request_data)

        try:
            with self.lock:
                result = self.interface.write(request_report)
        except Exception as e:
            return False, f"Exception: {e}"

        return True, result

    def send(self, data: bytearray, timeout: int = 15) -> tuple[bool, Any]:
        """ Write a data report and read the response, the result of the response will be ignored"""

        if self.interface is None:
            return False, "No Interface"

        request_data = [0x00] * (self.settings.HID_REPORT_SIZE + 1) # First byte is Report ID
        request_data[1:len(data) + 1] = data
        request_report = bytes(request_data)

        try:
            with self.lock:
                result = self.interface.write(request_report)
                self.interface.read(self.settings.HID_REPORT_SIZE, timeout=timeout)
        except Exception as e:
            return False, f"Exception: {e}"

        return True, result

    def send_multiple(self, data: bytearray, received_lock: threading.Lock) -> tuple[bool, Any, threading.Lock]:
        if self.interface is None:
            return False, "No Interface", received_lock

        request_data = [0x00] * (self.settings.HID_REPORT_SIZE + 1) # First byte is Report ID
        request_data[1:len(data) + 1] = data
        request_report = bytes(request_data)

        try:
            if received_lock is None:
                self.lock.acquire()
            elif received_lock != self.lock:
                return False, "Lock mismatch", received_lock
            if not self.lock.locked():
                return False, "Not locked", self.lock

            result = self.interface.write(request_report)
        except Exception as e:
            self.lock.release()
            return False, f"Exception: {e}", self.lock

        return True, result, self.lock

    def drain_read_buffer(self, num_msgs: int, received_lock: threading.Lock) -> tuple[bool, int, str, threading.Lock]:
        if self.interface is None:
            return False, 0, "No Interface", received_lock
        num_drained = 0
        try:
            if received_lock is None:
                self.lock.acquire()
            elif received_lock != self.lock:
                return False, num_drained, "Lock mismatch", received_lock
            if not self.lock.locked():
                return False, num_drained, "Not locked", self.lock

            for _ in range(num_msgs):
                if len(self.interface.read(self.settings.HID_REPORT_SIZE, timeout=100)) > 0:
                    num_drained += 1
        except Exception as e:
            self.lock.release()
            return False, num_drained, f"Exception: {e}", self.lock

        return True, num_drained, "", self.lock
    
    def read(self, timeout: int) -> tuple[bool, bytearray]:
        if self.interface is None:
            return False, bytearray("No Interface")

        try:
            with self.lock:
                response_report = self.interface.read(self.settings.HID_REPORT_SIZE, timeout=timeout)
        except Exception as e:
            return False, bytearray(f"Exception: {e}")

        return True, response_report

    def read_with_lock(self, timeout: int, received_lock: threading.Lock) -> tuple[bool, bytearray, threading.Lock]:
        if self.interface is None:
            return False, "No Interface", received_lock

        try:
            if received_lock is None:
                self.lock.acquire()
            elif received_lock != self.lock:
                return False, bytearray("Lock mismatch"), received_lock
            if not self.lock.locked():
                return False, bytearray("Not locked"), self.lock

            response_report = self.interface.read(self.settings.HID_REPORT_SIZE, timeout=timeout)
        except Exception as e:
            return False, bytearray(f"Exception: {e}"), self.lock

        return True, response_report, self.lock

    def send_and_read_validate(self, data: bytearray, timeout: int, expected_prefix: bytearray) -> tuple[bool, bytearray]:
        lock = None
        result, reply, lock = self.send_and_read_validate_with_lock(data, timeout, expected_prefix, lock)
        if lock:
            lock.release()
        return result, reply

    def send_and_read_validate_with_lock(self, data: bytearray, timeout: int, expected_prefix: bytearray, received_lock: threading.Lock) -> tuple[bool, bytearray, threading.Lock]:
        try:
            if received_lock is None:
                self.lock.acquire()
            elif received_lock != self.lock:
                return False, bytearray("Lock mismatch"), received_lock
            if not self.lock.locked():
                return False, bytearray("Not locked"), self.lock

            request_data = [0x00] * (self.settings.HID_REPORT_SIZE + 1)  # First byte is Report ID
            request_data[1:len(data) + 1] = data
            request_report = bytes(request_data)

            self.interface.write(request_report)
            response_report = self.interface.read(self.settings.HID_REPORT_SIZE, timeout=timeout)
            if not response_report.startswith(expected_prefix):
                response_report = self.interface.read(self.settings.HID_REPORT_SIZE, timeout=timeout)
            else:
                return True, response_report, self.lock
        except Exception as e:
            self.lock.release()
            return False, bytearray(f"Exception: {e}"), self.lock

        return response_report.startswith(expected_prefix), response_report, self.lock
    
    def send_and_read(self, data: bytearray, timeout: int) -> tuple[bool, bytearray]:
        if self.interface is None:
            return False, bytearray("No Interface")

        request_data = [0x00] * (self.settings.HID_REPORT_SIZE + 1) # First byte is Report ID
        request_data[1:len(data) + 1] = data
        request_report = bytes(request_data)

        try:
            with self.lock:
                self.interface.write(request_report)
                response_report = self.interface.read(self.settings.HID_REPORT_SIZE, timeout=timeout)
        except Exception as e:
            return False, bytearray(f"Exception: {e}")

        return True, response_report
