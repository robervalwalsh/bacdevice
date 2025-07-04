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

import numpy as np
import pandas as pd

import thermorasp
import dustmeter

# https://influxdb-client.readthedocs.io/en/stable/index.html
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

METERS = { "thermorasps": thermorasp , "dustmeters": dustmeter }

## Example dataclass
# from dataclasses import dataclass
# @dataclass
# class Point:
#     x: int
#     y: int

def get_influx_info(): # see you .basrc, zshrc, etc.
    return os.environ.get("INFLUX_URL_CMSDAF"),os.environ.get("INFLUX_ORG_CMSDAF"),os.environ.get("INFLUX_BUCKET_IRSETUP"),os.environ.get("INFLUX_TOKEN_IRSETUP")

def dew_point(t,rh):
# refs:
# https://iridl.ldeo.columbia.edu/dochelp/QA/Basic/dewpoint.html
# https://journals.ametsoc.org/view/journals/bams/86/2/bams-86-2-225.xml
    Rw = 461.5
    tk = t+273.15
    L = vapour_enthalpy(tk)
    td = tk/(1.-tk*np.log(rh/100)/(L/Rw))
    td -= 273.15
    return td
    
def vapour_enthalpy(t):
# refs:
# https://journals.ametsoc.org/view/journals/bams/86/2/bams-86-2-225.xml
    t1 = 273.15
    L1 = 2.501E6
    t2 = 373.15
    L2 = 2.257E6
    b = (L1-L2)/(t1-t2)
    a = L1 - b*t1
    L = a + b*(t)
    return L


def readout(meters):
    measurements = {}
    unixtime = int(time.time())

    for meter in meters :
        section = meter.getSection()
        if not section in measurements:
            measurements[section] = [None]*4
        fname = meter.name
        outputvar = meter.getPresentValue ( )
        if type(outputvar).__name__ == 'list':
            continue
        if 'rasp' in fname:
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
        if 'dustmeter' in fname:
            measurements[section][0] = datetime.strptime(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),'%Y-%m-%d %H:%M:%S').replace ( microsecond = 0 )
            if 'small' in fname:
                measurements[section][1] = outputvar
            elif 'large' in fname:
                measurements[section][2] = outputvar
            else:
                print('Invalid measurement for ',fname)
                continue
                
    return measurements

def store():
    global prev_timestamp
    global store_path
    global update_interval
    global meter_name
    global meter_type
    global time_interval
    global sleep_time
    
    global db_url
    global db_token
    global db_org
    global db_bucket
    
    global db_client
    global db_write_api
    
    global keyword
    global measurement_type
    
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
        

        
        db_structure = {} 
        measurement['timestamp_utc'] = [values[0]]
        meter_timestamp = int(measurement['timestamp_utc'][0].replace(tzinfo=pytz.UTC).timestamp())
        if 'rasp' in key:
            # measurement['timestamp_utc'] = [values[0]]
            # meter_timestamp = int(measurement['timestamp_utc'][0].replace(tzinfo=pytz.UTC).timestamp())
            if values[1]:
                measurement['temperature'] = [values[1]]
            if values[2] and values[3]:
                measurement['pressure'] = [values[2]]
                measurement['humidity'] = [values[3]]
                dew_point_value = dew_point(measurement['temperature'][0],measurement['humidity'][0])
                db_structure = {
                    "measurement": measurement_type,
                    "tags": {"sensor_type": meter_type[key], "sensor_position": meter_name[key]},
                    "fields": {"temperature": measurement['temperature'][0], 
                               "pressure": measurement['pressure'][0], 
                               "relative_humidity": measurement['humidity'][0],
                               "dew_point": dew_point_value},
                    "time": meter_timestamp
                }
            else:
                db_structure = {
                    "measurement": measurement_type,
                    "tags": {"sensor_type": meter_type[key], "sensor_position": meter_name[key]},
                    "fields": {"temperature": measurement['temperature'][0]},
                    "time": meter_timestamp
                }
                
        if 'dust' in key:
            # measurement['timestamp_utc'] = [values[0]]
            # meter_timestamp = int(measurement['timestamp_utc'][0].timestamp())
            measurement['small'] = [values[1]]
            measurement['large'] = [values[2]]
            db_structure = {
                "measurement": measurement_type,
                "tags": {"sensor_type": meter_type[key], "sensor_position": meter_name[key]},
                "fields": {"small_particles": measurement['small'][0],
                           "large_particles": measurement['large'][0]},
                "time": meter_timestamp
            }            
           
        point = Point.from_dict(db_structure, WritePrecision.S)
        
        df = pd.DataFrame(data=measurement)
        
        
        if store_path:
            filename = f"{keyword}_{meter_type[key]}_{meter_name[key]}.csv"
            output_csv = '{}/{}'.format(store_path,filename)
            header = ( not os.path.exists(output_csv) )
            df.to_csv(output_csv, mode='a', header=header, index=False)
            
        if db_client and db_write_api:
            db_write_api.write(bucket=db_bucket, org=db_org, record=point)
            # point = (
            # Point("environment")
            # .tag("sensor_type", meter_type[key])
            # .tag("sensor_position", meter_name[key])
            # .field("temperature", temps[value])
            # .time(timestamps[value], write_precision='ns')
            # )



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
    global meter_type
    global time_interval
    global sleep_time
    
    global db_url
    global db_token
    global db_org
    global db_bucket
    
    global db_client
    global db_write_api
    
    global keyword
    global measurement_type
    
    db_client = None
    db_write_api = None
    
    store_path = ""

    meter_name = {}
    meter_type = {}
    prev_timestamp = {}
    time_interval = {}
    sleep_time = 10
    update_interval = {}
    
    db_url = ""
    db_token = ""
    db_org = ""
    db_bucket = ""
    
    home_path = os.environ.get('HOME')
    
#    server_config = 'server.cfg'
    if len(sys.argv) > 1:
        server_config = sys.argv[1]
    else:
        print("Error: Please provide the name of configuration file")
        exit(1)
    if not path.exists ( server_config ) :
        print("Error: File " + server_config + " not found.")
        logger.error ( "Error: File " + server_config + " not found." )
        exit ( 1 )

    cparser = configparser.ConfigParser ( )
    cparser.read ( server_config )

    if not "server" in cparser :
        logger.error ( "Invalid config: No server section" )
        exit ( 1 )

    required_keys = { "ip", "port", "objectname", "vendoridentifier", "location", "vendorname", "modelname", "description", "keyword", "measurement" }
    missing_keys = required_keys - set ( cparser["server"].keys ( ) )
    if len ( missing_keys ) != 0 :
        logger.error ( "Missing config keys in server section: " + ( " ".join ( missing_keys ) ) )
        exit ( 1 )

    meters_active = []
    ai_objs = []
    idx = 1
    
    keyword = cparser["server"]["keyword"]
    measurement_type = cparser["server"]["measurement"]

    store_path_default = f'{home_path}/daf-monitoring/data'
    if 'path' in cparser['storage']:
        store_path = f"{store_path_default}/{cparser['storage']['path']}"
        os.makedirs(store_path,exist_ok=True)


    if 'database_url' in cparser['storage']:
        db_url = os.environ.get(cparser['storage']['database_url'])
        db_token = os.environ.get(cparser['storage']['token'])
        db_org = os.environ.get(cparser['storage']['organization'])
        db_bucket = os.environ.get(cparser['storage']['bucket'])
        if not db_url or not db_token or not db_org or not db_bucket:
            logger.error("Please check your configuration file: database_url, token, organization and bucket must be set in storage section")
            exit(1)
        db_client = InfluxDBClient(url=db_url, token=db_token, org=db_org)
        db_write_api = db_client.write_api(write_options=SYNCHRONOUS)

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
            meter_type[metersection] = ""
            if "meter_type" in info:
                meter_type[metersection] = info["meter_type"]
            
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
    
