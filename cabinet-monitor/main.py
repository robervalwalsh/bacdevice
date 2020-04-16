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
import time
from collections import OrderedDict
from math import pi

from bokeh.plotting import figure, curdoc
from bokeh.driving import linear
from bokeh.models import DatetimeTickFormatter
from bokeh.models.widgets import Div,PreText
from bokeh.layouts import column,row
from bokeh.application.handlers.directory import DirectoryHandler

import random

import pandas as pd


import thermorasp
METERS = { "thermorasps": thermorasp }

#unixtime = time.time()
#data = -273.

def readout(meters):
    global unixtime
    global data
#    time.sleep ( 10 )
    measurements = {}
    for meter in meters :
        section = meter.getSection()
        if not section in measurements:
            measurements[section] = [None]*4
        fname = meter.name
        outputvar = meter.getPresentValue ( )
        measurements[section][0] = datetime.strptime(meter.getPresentDate ( ),'%Y-%m-%d %H:%M:%S.%f') .replace ( microsecond = 0 )
        if 'temp' in fname:
            measurements[section][1] = outputvar
        elif 'pres' in fname:
            measurements[section][2] = outputvar
        elif 'hum' in fname:
            measurements[section][3] = outputvar
        else:
            print('Invalid measurement for ',fname)
            continue

        var_date = datetime.strptime(meter.getPresentDate ( ),'%Y-%m-%d %H:%M:%S.%f') .replace ( microsecond = 0 )

    unixtime = int(time.time())
    data = measurements['raspberry3-bus1-ch1'][1]
    point  = [var_date,data]
#    print(measurements)
    return measurements

def store():
    time.sleep(10)
    measurements = readout(mymeters)
    print(measurements)
    for key,values in measurements.items():
        rasp = key.split('-')[0]
        sensor = key
        timestamp = [int(time.mktime(values[0].timetuple()))]
        measurement = {'temperature':[values[1]],'pressure':[values[2]],'humidity':[values[3]]}
        df = pd.DataFrame(data=measurement,index=timestamp)
        print(df)
#        df.to_hdf('{}.h5'.format(rasp), key=sensor, format='table', append=True)


@linear()
def update(step):
    measurements = readout(mymeters)
    # datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    date1 = measurements['raspberry3-bus1-ch1'][0]
    temp1 = measurements['raspberry3-bus1-ch1'][1]
    ds1.data['x'].append(date1)
    ds1.data['y'].append(temp1)
    ds1.trigger('data', ds1.data, ds1.data)
    date2 = measurements['raspberry3-bus4-ch1'][0]
    temp2 = measurements['raspberry3-bus4-ch1'][1]
    ds2.data['x'].append(date2)
    ds2.data['y'].append(temp2)
    ds2.trigger('data', ds2.data, ds2.data)
    date3 = measurements['raspberry3-bus4-ch0'][0]
    temp3 = measurements['raspberry3-bus4-ch0'][1]
    ds3.data['x'].append(date3)
    ds3.data['y'].append(temp3)
    ds3.trigger('data', ds3.data, ds3.data)
    
    pre_head2.update(text="     Present values")
    pre_temp_top.update(text="     Top sensor tempearture   : {} C".format(temp1))
    pre_temp_mid.update(text="     Middle sensor tempearture: {} C".format(temp2))
    pre_temp_bot.update(text="     Bottom sensor tempearture: {} C".format(temp3))

    
    deltaT = (ds1.data['x'][-1]-ds1.data['x'][0]).seconds
    if  deltaT > 1800:
        del ds1.data['x'][0] 
        del ds1.data['y'][0] 
        del ds2.data['x'][0] 
        del ds2.data['y'][0] 
        del ds3.data['x'][0] 
        del ds3.data['y'][0] 
    
    

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

    server_config = 'server.cfg'
    if __name__.startswith('bk_script'):
        server_config = 'cabinet-monitor/server.cfg'
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
    while True:
        store()
    
elif __name__.startswith('bk_script'):
    # name starts with bk_script (__name__ = bk_script_<some number>)
    div = Div(text="<img src='cabinet-monitor/static/daf_25c_cabinet_sensors_test.jpg' width='300'>")
    p = figure(plot_width=800, plot_height=500,x_axis_type="datetime")
    date_format = ['%d %b %Y %H:%M:%S']
    p.xaxis.formatter=DatetimeTickFormatter(
           microseconds=date_format,
           milliseconds=date_format,
           seconds=date_format,
           minsec=date_format,
           minutes=date_format,
           hourmin=date_format,
           hours=date_format,
           days=date_format,
           months=date_format,
           years=date_format
    )
    p.xaxis.major_label_orientation = pi/3
    p.xaxis.axis_label = "Local time"
    p.yaxis.axis_label = "Temperature (C)"
    
    r1 = p.line([], [], color="firebrick", line_width=2,legend_label='top')
    r2 = p.line([], [], color="navy", line_width=2,legend_label='middle')
    r3 = p.line([], [], color="green", line_width=2,legend_label='bottom')
    
    p.legend.location = "top_left"


    ds1 = r1.data_source
    ds2 = r2.data_source
    ds3 = r3.data_source
    
    pre_head = PreText(text="N.B.: Readout every 10 seconds. Be patient!",width=500, height=50)
    pre_head2 = PreText(text="",width=400, height=25)
    pre_temp_top = PreText(text="",width=400, height=20)
    pre_temp_mid = PreText(text="",width=400, height=20)
    pre_temp_bot = PreText(text="",width=400, height=20)
    
    curdoc().add_root(column(pre_head,row(div,column(pre_head2,pre_temp_top,pre_temp_mid,pre_temp_bot),p,)))
    
    main()
#    time.sleep ( 10 )
    curdoc().add_periodic_callback(update, 10000)
else:
    pass    
