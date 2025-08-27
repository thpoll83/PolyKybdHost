import serial.tools.list_ports

class SerialHelper:
    def __init__(self, vid, pid):
        self.pid = pid
        self.vid = vid
        self.serial = self.find_serial()
        self.buffer = ""
        
    def find_serial(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.vid is not None and port.pid is not None:
                if port.vid == self.vid and port.pid == self.pid:
                    return port.device
        return None

    def read_all(self):
        return self.serial.read_all() if self.serial != None else None
    
    def read_all_and_add_to_buffer(self):
        data = self.read_all()
        if data != None:
            self.buffer += data.encode("utf-8")
    
    def get_buffer(self):
        return self.buffer
    
    def reset_buffer(self):
        self.buffer = ""
