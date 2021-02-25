#!/usr/bin/env python3

# Main program to broadcast data points to the DESY BACNet
# --------------------------------------------------------

# running bokeh server:
# bokeh serve cabinet-monitor --address fhlcleangate.desy.de --port 5002 --allow-websocket-origin=fhlcleangate.desy.de:5002

import sys
import pathlib
import os
from os import path

pwd = str(pathlib.Path().absolute())
wd = pwd
proj_name = pwd.split('/')[-1]
if proj_name != 'bacdevice':
    wd = pwd+'/..'
sys.path.append(wd)

logsdir = wd+'/logs'

import logging
logger = logging.getLogger ( 'mylivelog' )
logger.setLevel ( logging.DEBUG )
logname = logsdir+'/'+__name__+'_output_live.log'
if __name__ == '__main__':
    logname = logsdir+'/'+proj_name+'_output.log'
fh = logging.FileHandler ( logname )
fh.setLevel ( logging.DEBUG )
logger.addHandler ( fh )

import configparser
from sys import exit, version_info
import threading
import time
import pytz
from uuid import getnode

import csv
import sys
from datetime import datetime
from datetime import date
import time
from collections import OrderedDict
from math import pi


import random

import pandas as pd


import thermorasp
METERS = { "thermorasps": thermorasp }

def readout(meters):
    measurements = {}
    for meter in meters :
        section = meter.getSection()
        if not section in measurements:
            measurements[section] = [None]*4
        fname = meter.name
        outputvar = meter.getPresentValue ( )
        try:
            measurements[section][0] = datetime.strptime(meter.getPresentDate ( ),'%Y-%m-%d %H:%M:%S.%f').replace ( microsecond = 0 )
        except ValueError as ve1:
            try:
                measurements[section][0] = datetime.strptime(meter.getPresentDate ( ),'%Y-%m-%d %H:%M:%S').replace ( microsecond = 0 )
            except ValueError as ve2:
                continue
        if 'temp' in fname:
            measurements[section][1] = outputvar
        elif 'pres' in fname:
            measurements[section][2] = outputvar
        elif 'hum' in fname:
            measurements[section][3] = outputvar
        else:
            print('Invalid measurement for ',fname)
            continue

    unixtime = int(time.time())
    return measurements

def store():
    global prev_timestamp
    global store_path
    global update_interval
    global meter_name
    global time_interval
    global sleep_time
#    time.sleep(10)
    measurements = readout(mymeters)
    if measurements == {}:
        return
    for key,values in measurements.items():
        # trying to deal with phase difference between data readout and storage intervals
        if time_interval[key] < update_interval[key]:
            time_interval[key] += sleep_time
            continue
        time_interval[key] = sleep_time
       
#        rasp = key.split('-')[0]
#        sensor = key.replace('-','_')
        try:
            timestamp = [int(time.mktime(values[0].timetuple()))]
        except  AttributeError as att_err:
            continue
        if timestamp == prev_timestamp[key]:
            continue
        else:
            prev_timestamp[key] = timestamp
            
#        measurement = {'time':[values[0]],'temperature':[values[1]],'pressure':[values[2]],'humidity':[values[3]]}
        measurement = {}

        measurement['timestamp_utc'] = [values[0]]
        if values[1]:
            measurement['temperature'] = [values[1]]
        if values[2] or values[3]:
            measurement['pressure'] = [values[2]]
            measurement['humidity'] = [values[3]]
        
        df = pd.DataFrame(data=measurement)
        
        output_csv = '{}/{}.csv'.format(store_path,meter_name[key])
        header = ( not os.path.exists(output_csv) )
        
        df.to_csv(output_csv, mode='a', header=header, index=False)


class DataThread ( threading.Thread ) :
    def __init__ ( self, meters ) :
        threading.Thread.__init__ ( self )
        threading.Thread.setName ( self, "dataThread" )
        self.meters = meters
        self.flag_stop = False

    def run ( self ) :
        while not self.flag_stop :
            time.sleep ( 10 )
            measurements = {}
            for meter in self.meters :
                section = meter.getSection()
                if not section in measurements:
                    measurements[section] = [None]*3
                fname = meter.name
                outputvar = meter.getPresentValue ( )
                if 'temp' in fname:
                    measurements[section][0] = outputvar
                elif 'pres' in fname:
                    measurements[section][1] = outputvar
                elif 'hum' in fname:
                    measurements[section][2] = outputvar
                else:
                    print('Invalid measurement for ',fname)
                    continue
                    
                var_date = datetime.datetime.strptime(meter.getPresentDate ( ),'%Y-%m-%d %H:%M:%S.%f') .replace ( microsecond = 0 )
                
            unixtime = int(time.time())
            data = measurements['raspberry3-bus1-ch1'][0]

            print(unixtime,data)
            print('---')

    def stop ( self ) :
        self.flag_stop = True



def main ( ) :
    global mymeters
    
    global update_interval
    global prev_timestamp
    global store_path
    global meter_name
    global time_interval
    global sleep_time
    
    meter_name = {}
    prev_timestamp = {}
    time_interval = {}
    sleep_time = 10
    update_interval = {}
    
    server_config = 'server.cfg'
    if not path.exists ( server_config ) :
        logger.error ( "Error: File server.cfg not found." )
        exit ( 1 )

    cparser = configparser.ConfigParser ( )
    cparser.read ( server_config )

    if not "server" in cparser :
        logger.error ( "Invalid config: No server section" )
        exit ( 1 )

    required_keys = { "ip", "port", "objectname", "vendoridentifier", "location", "vendorname", "modelname", "description" }
    missing_keys = required_keys - set ( cparser["server"].keys ( ) )
    if len ( missing_keys ) != 0 :
        logger.error ( "Missing config keys in server section: " + ( " ".join ( missing_keys ) ) )
        exit ( 1 )

    meters_active = []
    ai_objs = []
    idx = 1

    store_path = './'
    if 'path' in cparser['storage']:
         store_path = cparser['storage']['path']

    logger.info ( "Initializing meters..." )
    for key, metermodule in sorted(METERS.items(),reverse=True) :
        if not key in cparser["server"] :
            logger.warning ( "No key '{}' in config server section. Skipping" .format ( key ) )
            continue
        metersections = cparser["server"][key].split ( )
        missing_metersections = set ( metersections ) - set ( cparser.keys ( ) )
        if len ( missing_metersections ) != 0 :
            logger.error ( "Missing config sections for meters: " + "" .join ( missing_metersections ) )
            exit ( 1 )

        for metersection in metersections :
            info = cparser[metersection]

            # for a sensor there is three meters: temp, hum, pres
            # code is for one sensor in one raspberry
            ms = metermodule.getMeters ( info )
            logger.info ( "Got {} meter(s) from {}" .format ( len ( ms ), metersection ) )
            meters_active.extend ( ms )
            
            if "name" in info :
                if info["name"] in meter_name.values():
                    print('Please check your configuration file: different sensors with same name in config file')
                    os.sys.exit(-1)
                meter_name[metersection] = info["name"]
            else:
                meter_name[metersection] = metersection
            prev_timestamp[metersection] = [0]
            
            update_interval[metersection] = 60
            if "updateInterval" in info:
                update_interval[metersection] = int(info["updateInterval"])
                
            if update_interval[metersection] < 10:
                update_interval[metersection] = 10
            update_interval[metersection] = round(update_interval[metersection]/10)*10
            
            # initially just grab the first data available
            time_interval[metersection] = update_interval[metersection]
            
            for m in ms :
                m.name = "{}_{}" .format ( metersection, m.name )
                m.section = metersection
                
                idx += 1

                fname = m.name


    mymeters = meters_active
    for m in meters_active :
        m.start ( )

#    datathread = DataThread ( meters_active )
#    datathread.start ( )

    
#    while True:
#        pass
    
#    datathread.stop ( )
#    datathread.join ( )

#    for m in meters_active :
#        m.stop ( )
#        m.join ( )


if __name__ == "__main__" :
    main ( )
    # allow some time to have data from network(???)
    time.sleep(1)
    
    while True:
        store()
        time.sleep(sleep_time)
    
