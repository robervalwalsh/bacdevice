#!/usr/bin/env python3

import submeter
import socket
import threading

class PumpstationMeter(submeter.SubMeter):
    def __init__(self, name, pumpstation):
        submeter.SubMeter.__init__(self, name, pumpstation)
        
class PumpstationError(Exception):
    def __init__(self, name, host, port, msg):
        self.name = name
        self.host = host
        self.port = port
        self.msg = msg
        
    def __str__(self):
        return "Error from {}#{}:{}: {}".format(self.name, self.host, self.port, self.msg)
        
class Pumpstation(threading.Thread):
    defaultProps = {
        "name": "Pumpstation",
        "host": "localhost",
        "port": 63432,
        "reconnect": False
    }
    
    ERROR_SLEEP = 30 #seconds to sleep after error
    SLEEP_TIME = 30 #seconds to sleep after refresh
    SOCKET_TIMEOUT = 5 #seconds to wait for socket
    
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        for attr, value in Pumpstation.defaultProps.items():
            if attr not in kwargs:
                kwargs[attr] = value        
        self.name = kwargs["name"]
        self.host = kwargs["host"]
        try:
            self.port = int(kwargs["port"])
        except ValueError:
            print("Invalid port " + kwargs["port"])
            return
        self.reconnect = kwargs['reconnect']
        self._stop_event = threading.Event()
        self.press = [PumpstationMeter("PSYS", self),
                        PumpstationMeter("P1", self),
                        PumpstationMeter("P2", self)]
        self.switches = [PumpstationMeter("PUMP1STATUS", self),
                        PumpstationMeter("PUMP2STATUS", self),
                        PumpstationMeter("V1", self),
                        PumpstationMeter("V2", self),
                        PumpstationMeter("V3", self)]
        self.pumps = [PumpstationMeter("PUMP1HOURS", self),
                        PumpstationMeter("PUMP2HOURS", self)]
        
    def run(self):
        while not self._stop_event.is_set():
            try:
                self._updatePressures()
                self._updateSwitches()
                self._updatePumps()
            except PumpstationError as e:
                self._setAllIsConnStatus(False)
                print(e)
                if self.reconnect:
                    self._stop_event.wait(self.ERROR_SLEEP)
                    continue
                break
            self._stop_event.wait(self.SLEEP_TIME)
                
    def _updatePressures(self):    
        values = self._do_command("getVacuumStatus", [int]*3 + [float]*3)
        statuses = values[:3]
        values = values[3:]
            
        for i, press in enumerate(self._press):
            press.is_connected = status[i] == 1
            press.present_value = values[i]
            
    def _updateSwitches(self):            
        values = self._do_command("getSwitchStatus", [bool]*5)
            
        for i, switch in enumerate(self.switches):
            switch.is_connected = True
            switch.present_value = values[i]
            
    def _updateSwitches(self):
        values = self._do_command("getPumpOperatingHours", [float]*2)
            
        for i, pump in enumerate(self.pumps):
            pump.is_connected = True
            pump.present_value = values[i]
            
    def _do_command(self, command, types):
        s = self._openSocket()
        try:
            self._sendCommand(s, command)
            resp = self._recvResponse(s)
            if resp.count(";") != len(types) - 1:
                raise RuntimeError("Invalid response from server")
        except (RuntimeError, socket.error, socket.timeout) as e:
            raise PumpstationError(self.name, self.host, self.port, str(e)) from e
        finally:
            s.close()
        values = resp.split(";")
        try:
            values = [types[i](val) for i, val in enumerate(values)]
        except ValueError as e:
            raise PumpstationError(self.name, self.host, self.port, "Invalid value in response") from e
            
        return values
        
    def _openSocket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.SOCKET_TIMEOUT)
        if s.connect_ex((self.host, self.port)) != 0:
            s.close()
            raise PumpstationError(self.name, self.host, self.port, "Could not connect.")
        return s
                    
    def _sendCommand(self, socket, command):
        data = len(command).to_bytes(2, "little")
        data += bytes(command, "utf-8")
        data += b"\0"
        
        socket.sendall(data)
            
    def _recvResponse(self, socket):
        data = b""
        while not self._stop_event.is_set():
            new_data = socket.recv(64)
            if len(new_data) == 0:
                break
            data += new_data
        blocksize = int.from_bytes(data[:2], "little")
        resp = data[2:-1].decode("utf-8")
        
        return resp
        
    def _setAllIsConnStatus(self, status):
        for meter in self.press + self.switches + self.pumps:
            meter.is_connected = status
        
    def stop(self):
        self._stop_event.set()
        
def getMeters(config):
    pump = Pumpstation(**config)
    return pump.press + pump.switches + pump.pumps
    
if __name__ == "__main__":
    pass
