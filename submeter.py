#!/usr/bin/env python3

import meter_base

class SubMeter(meter_base.MeterBase):
    def __init__(self, name, parent):
        self._parent = parent
        self.name = name
        self.is_connected = False
        self.present_value = 0
        
    def start(self):
        try:
            self._parent.start()
        except RuntimeError:
            pass
            
    def stop(self):
        self._parent.stop()
        
    def join(self):
        self._parent.join()
        
    def getPresentValue(self):
        return self.present_value
