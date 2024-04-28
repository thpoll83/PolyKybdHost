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

        device_interfaces = hid.enumerate(vid, pid)
        raw_hid_interfaces = [i for i in device_interfaces if i['usage_page'] == usage_page and i['usage'] == usage]

        if len(raw_hid_interfaces) != 0:
            self.interface = hid.Device(path=raw_hid_interfaces[0]['path'])
        else:
            self.interface = None

    def interface_aquired(self):
        return self.interface != None

    def send_raw_report(self, data):

        if self.interface is None:
            return False, "No Interface"

        request_data = [0x00] * (report_length + 1) # First byte is Report ID
        request_data[1:len(data) + 1] = data
        request_report = bytes(request_data)

        try:
            result = self.interface.write(request_report)
        except Exception as e:
            return False, f"Exception: {e}"
            
        return True, result
    
    def read_raw_report(self, timeout):

        if self.interface is None:
            return False, "No Interface"

        try:
            response_report = self.interface.read(report_length, timeout=timeout)
        except Exception as e:
            return False, f"Exception: {e}"
            
        return True, response_report

