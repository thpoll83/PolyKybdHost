import pathlib
import threading
import platform
if platform.system() == 'Windows':
    import ctypes
    import os 
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
            try:
                self.interface = hid.Device(path=raw_hid_interfaces[0]['path'])
            except hid.HIDException as e:
                print(f"""It looks like you do not have permission to access the device.
Please run the following commands, then reconnect the device and restart the application:

sudo cp {os.path.join(pathlib.Path(__file__).parent.resolve(), "99-hid.rules")} /etc/udev/rules.d
sudo udevadm control --reload-rules
sudo udevadm trigger
""")
                raise e
                
        else:
            self.interface = None

    def interface_acquired(self):
        return self.interface is not None

    def __send(self, data):
        """ Write a data report without reading the response"""

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

    def send(self, data, timeout = 15):
        """ Write a data report and read the response, the result of the response will be ignored"""

        if self.interface is None:
            return False, "No Interface"

        request_data = [0x00] * (report_length + 1) # First byte is Report ID
        request_data[1:len(data) + 1] = data
        request_report = bytes(request_data)

        try:
            with self.lock:
                result = self.interface.write(request_report)
                self.interface.read(report_length, timeout=timeout)
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
            if not self.lock.locked():
                return False, "Not locked", self.lock

            result = self.interface.write(request_report)
        except Exception as e:
            self.lock.release()
            return False, f"Exception: {e}"

        return True, result, self.lock

    def drain_read_buffer(self, num_msgs, received_lock):
        if self.interface is None:
            return False, "No Interface", received_lock
        num_drained = 0
        try:
            if received_lock is None:
                self.lock.acquire()
            elif received_lock != self.lock:
                return False, "Lock missmatch", received_lock
            if not self.lock.locked():
                return False, "Not locked", self.lock

            for _ in range(num_msgs):
               if len(self.interface.read(report_length, timeout=100)) > 0:
                   num_drained += 1
        except Exception as e:
            self.lock.release()
            return False, f"Exception: {e}"

        return num_drained, self.lock
    
    def read(self, timeout):
        if self.interface is None:
            return False, "No Interface"

        try:
            with self.lock:
                response_report = self.interface.read(report_length, timeout=timeout)
        except Exception as e:
            return False, f"Exception: {e}"

        return True, response_report.decode().strip('\x00')

    def read_with_lock(self, timeout, received_lock):
        if self.interface is None:
            return False, "No Interface", received_lock

        try:
            if received_lock is None:
                self.lock.acquire()
            elif received_lock != self.lock:
                return False, "Lock missmatch", received_lock
            if not self.lock.locked():
                return False, "Not locked", self.lock

            response_report = self.interface.read(report_length, timeout=timeout)
        except Exception as e:
            return False, f"Exception: {e}"

        return True, response_report.decode().strip('\x00'), self.lock

    def send_and_read_validate(self, data, timeout, expected_prefix):
        lock = None
        result, msg, lock = self.send_and_read_validate_with_lock(data, timeout, expected_prefix, lock)
        if lock:
            lock.release()
        return result, msg

    def send_and_read_validate_with_lock(self, data, timeout, expected_prefix, received_lock):
        result = False
        msg = ""
        try:
            if received_lock is None:
                self.lock.acquire()
            elif received_lock != self.lock:
                return False, "Lock missmatch", received_lock
            if not self.lock.locked():
                return False, "Not locked", self.lock

            request_data = [0x00] * (report_length + 1)  # First byte is Report ID
            request_data[1:len(data) + 1] = data
            request_report = bytes(request_data)

            self.interface.write(request_report)
            response_report = self.interface.read(report_length, timeout=timeout)
            msg = response_report.decode().strip('\x00')
            if not msg.startswith(expected_prefix):
                response_report = self.interface.read(report_length, timeout=timeout)
                msg = response_report.decode().strip('\x00')
            else:
                return True, msg, self.lock
        except Exception as e:
            self.lock.release()
            return False, f"Exception: {e}"

        return msg.startswith(expected_prefix), msg, self.lock
    
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
