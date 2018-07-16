#!/usr/bin/env python2

import logging
logger = logging.getLogger('mybaclog')
import threading
import socket
from time import sleep, time
from datetime import datetime
import re

import submeter

class ThermoRaspMeter(submeter.SubMeter):
    def __init__(self, name, thermorasp):
        submeter.SubMeter.__init__(self, name, thermorasp)

class TermoRasp(threading.Thread):
    defaultProps = {
        "name": "ThermoRasp",
        "host": "localhost",
        "port": 50007,
    }

    SLEEP_TIME = 5 #seconds to sleep after refresh
    MAX_REFRESH_TIME = 600 #seconds after which the sensors will be
                        #deemed disconnected if there was no timestamp change
    SOCKET_TIMEOUT = 10 #seconds to wait for socket

    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        for attr, value in TermoRasp.defaultProps.items():
            if attr not in kwargs:
                kwargs[attr] = value        
        self.name = kwargs["name"]
        self.host = kwargs["host"]
        self._stop_event = threading.Event()
        self.meters = {}

        try:
            self.port = int(kwargs["port"])
        except ValueError:
            logger.error("Invalid port " + kwargs["port"])
            return

        logger.info("Initiating {} at {}:{}".format(self.name, self.host, self.port))
        r = self.getReadings()
        if not r:
            logger.error("Failed to connect to {} at {}:{} at {}".format(self.name, self.host, self.port, datetime.now()))
            return
        lines = r.split("\n")
        fields = lines[0].split()
        meter_names = fields[2:]

        if len(lines) < 2:
            logger.warning("Invalid reply from {} at {}:{} at {}".format(self.name, self.host, self.port, datetime.now()))
            return
        self._ts_offset = time() - self._parseTimestamp(lines[1])

        for name in meter_names:
            self.meters[name] = ThermoRaspMeter(name, self)

    def run(self):
        while not self._stop_event.is_set():
            r = self.getReadings()
            if not r:
                logger.warning("No reply from {} at {}:{} at {}".format(self.name, self.host, self.port, datetime.now()))
                self._setAllIsConnStatus(False)
                sleep(self.SLEEP_TIME)
                continue
            lines = r.split("\n")
            if len(lines) < 2:
                print("Invalid reply from {} at {}:{} at {}".format(self.name, self.host, self.port, datetime.now()))
                self._setAllIsConnStatus(False)
                sleep(self.SLEEP_TIME)
                continue
            fields = lines[0].split()
            meter_names = fields[2:]

            readings = lines[1].split(" ")[2:]
            for i, name in enumerate(meter_names):
                try:
                    reading = float(readings[i])
                except ValueError:
                    self.meters[name].is_connected = False
                    logger.debug("Invalid or empty value for {} of {} at {}:{}".format(name, self.name, self.host, self.port))
                    continue
                self.meters[name].present_value = reading
                self.meters[name].is_connected = True
                logger.debug("Data from {} at {}:{} at {} is: {}: {}".format(self.name, self.host, self.port, datetime.now(), name, reading))

            if abs(time() - self._parseTimestamp(lines[1]) - self._ts_offset) > self.MAX_REFRESH_TIME:
                self._setAllIsConnStatus(False)

            sleep(self.SLEEP_TIME)

    def stop(self):
        self._stop_event.set()

    def getReadings(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.SOCKET_TIMEOUT)
        if s.connect_ex((self.host, self.port)) != 0:
            return None
        data = b""
        new_data_len = 1
        while new_data_len != 0:
            new_data = s.recv(64)
            new_data_len = len(new_data)
            data += new_data
        s.close()
        return data.decode("utf-8")

    def _parseTimestamp(self, date_str):
        if re.match("\\d+-\\d+-\\d+T\\d+:\\d+:\\d+\\.\\d+", date_str):
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f").timestamp()
        elif re.match("\\d+-\\d+-\\d+T\\d+:\\d+:\\d+", date_str):
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S").timestamp()
        else:
            return 0

    def _setAllIsConnStatus(self, status):
        for name, meter in self.meters.items():
            meter.is_connected = status

def getMeters(config):
    thermorasp = TermoRasp(**config)
    return list(thermorasp.meters.values())

if __name__ == "__main__":
    print(getMeters({"host": "fhlthermorasp", "port": 50007}))
