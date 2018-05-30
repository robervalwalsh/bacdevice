#!/usr/bin/env python3

import submeter
import socket
import threading
import select
import time
from datetime import datetime
from PyQt5.QtCore import QByteArray, QDataStream, QIODevice

class DustmeterMeter(submeter.SubMeter):
    def __init__(self, name, pumpstation):
        submeter.SubMeter.__init__(self, name, pumpstation)

class DustmeterError(Exception):
    def __init__(self, name, host, port, msg):
        self.name = name
        self.host = host
        self.port = port
        self.msg = msg

    def __str__(self):
        return "Error from {}#{}:{}: {}".format(self.name, self.host, self.port, self.msg)

class Dustmeter(threading.Thread):
    defaultProps = {
        "name": "myDustmeter",
        "host": "localhost",
        "port": 8888,
        "default_dust": 0,
        "reconnect": True
    }

    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        for attr, value in Dustmeter.defaultProps.items():
            if attr not in kwargs:
                kwargs[attr] = value
        self.name = kwargs["name"]
        self.host = kwargs["host"]
        self.port = kwargs["port"]
        self.reconnect = kwargs["reconnect"]
        self.dustvalues = [DustmeterMeter("dust_small", self), DustmeterMeter("dust_large", self)]
        #self.dust_large = kwargs["default_dust"]
        self.is_connected = False
        self.ev = threading.Event()
        print("Initiating {} at {}:{}".format(self.name, self.host, self.port))

    def run(self):
        while True:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if s.connect_ex((self.host, self.port)) == 0:
                self.is_connected = True
                print("Connected {} at {}:{}".format(self.name, self.host, self.port))
            else:
                self.is_connected = False
                print("No reply from {} at {}:{} at {}".format(self.name, self.host, self.port, datetime.now()))
                if self.reconnect:
                    print("Reconnected to {} at {}:{} at {}".format(self.name, self.host, self.port, datetime.now()))
                    time.sleep(30)
                    continue
                else:
                    print("Failed to reconnect to {} at {}:{} at {}".format(self.name, self.host, self.port, datetime.now()))
                    for i, dusts in enumerate(self.dustvalues):
                        dusts.is_connected = False
                        dusts.present_value = DustMeter.defaultProps['default_dust']
                    s.close()
                    break
            inout = [s]
            idel_loop_count = 0
            while True:
                infds, outfds, errfds = select.select(inout, [], [], 0.01)
                if len(infds) != 0:
                    time.sleep(0.1)
                    buf = s.recv(64)
                    if len(buf) != 0:
                        idel_loop_count = 0;
                        [small_str, large_str] = buf.split(b',')
                        smalldst = int(small_str)
                        largedst = int(large_str)
                        #print (self.name, '#', 'receive data:', repr(buf))
                        for i, dusts in enumerate(self.dustvalues):
                            dusts.is_connected = True
                            if (i==0):
                                dusts.present_value = smalldst
                            if (i==1):
                                dusts.present_value = largedst


                if self.ev.wait(30):
                    self.ev.clear()
                    print("Closed connection to {} at {}:{} at {}".format(self.name, self.host, self.port, datetime.now()))
                    for i, dusts in enumerate(self.dustvalues):
                        dusts.is_connected = False
                        dusts.present_value = DustMeter.defaultProps['default_dust']
                    s.close()
                    return
                else:
                    idel_loop_count += 1
                    if(idel_loop_count > 4):
                        print("No data, closing connection to {} at {}:{} at {}".format(self.name, self.host, self.port, datetime.now()))
                        for i, dusts in enumerate(self.dustvalues):
                            dusts.is_connected = False
                            dusts.present_value = DustMeter.defaultProps['default_dust']
                        s.close()
                        break

    def stop(self):
        self._stop_event.set()

def getMeters(config):
    dust = Dustmeter(**config)
    return dust.dustvalues

if __name__ == "__main__":
    pass
