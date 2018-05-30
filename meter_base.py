#!/usr/bin/env python3

import abc

class MeterBase(abc.ABC): 
    @abc.abstractmethod
    def start(self):
        pass

    @abc.abstractmethod
    def stop(self):
        pass

    @abc.abstractmethod
    def join(self):
        pass

    @abc.abstractmethod
    def getPresentValue(self):
        pass
