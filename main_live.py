#!/usr/bin/env python3

# Main program to broadcast data points to the DESY BACNet
# --------------------------------------------------------

import logging
logger = logging.getLogger ( 'mylivelog' )
logger.setLevel ( logging.DEBUG )
fh = logging.FileHandler ( 'output_live.log' )
fh.setLevel ( logging.DEBUG )
logger.addHandler ( fh )

import configparser
from sys import exit, version_info
import threading
import time
from uuid import getnode
from os import path

import csv
import os
import sys
import datetime
import time
from collections import OrderedDict

from bokeh.plotting import figure, curdoc
from bokeh.driving import linear
import random



import thermorasp
METERS = { "thermorasps": thermorasp }

unixtime = time.time()
data = -273.

p = figure(plot_width=400, plot_height=400)
r1 = p.line([], [], color="firebrick", line_width=2)
r2 = p.line([], [], color="navy", line_width=2)

ds1 = r1.data_source


@linear()
def update(step):
    ds1.data['x'].append(step)
    ds1.data['y'].append(data)
    ds1.trigger('data', ds1.data, ds1.data)
#     ds1.data['x'].append(step)
#     ds1.data['y'].append(random.randint(0,100))
#     ds1.trigger('data', ds1.data, ds1.data)
    
curdoc().add_root(p)

# Add a periodic callback to be run every 500 milliseconds
curdoc().add_periodic_callback(update, 1000)

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
                
#                 output_csv = os.path.join ( str ( '.' ), fname + u".csv" )
#                 mode = 'a'
#                 if sys.version_info.major < 3:
#                     mode += 'b'
#                 with open ( output_csv, mode ) as f :
#                     writer = csv.writer ( f, delimiter = ',' )
#                     writer.writerow ( [datetime.datetime.now ( ) .replace ( microsecond = 0 ) .isoformat ( " " ), outputvar] )
#                     f.close ( )

            unixtime = int(time.time())
            data = measurements['raspberry3-bus1-ch1'][1]

            print(unixtime,data)
            print('---')

    def stop ( self ) :
        self.flag_stop = True

def main ( ) :
#     p = figure(plot_width=400, plot_height=400)
#     r1 = p.line([], [], color="firebrick", line_width=2)
#     ds1 = r1.data_source
    
#     curdoc().add_root(p)


    if not path.exists ( "server.cfg" ) :
        logger.error ( "Error: File server.cfg not found." )
        exit ( 1 )

    cparser = configparser.ConfigParser ( )
    cparser.read ( "server.cfg" )

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
#                 output_csv = os.path.join ( str ( '.' ), fname + u".csv" )
#                 mode = 'a'
#                 if sys.version_info.major < 3:
#                     mode += 'b'
#                 with open ( output_csv, mode ) as f :
#                     header = OrderedDict ( [ ( '# time', None ), ( m.name, None ) ] )
#                     writer = csv.DictWriter ( f, fieldnames = header, extrasaction = u"ignore" )
#                     writer.writeheader ( )
#                     f.close ( )

    for m in meters_active :
        m.start ( )

    datathread = DataThread ( meters_active )
    datathread.start ( )

#     # Add a periodic callback to be run every 500 milliseconds
#     curdoc().add_periodic_callback(update, 100)
    
    data = 0.1
    while True:
        data +=0.1 
        pass
    
    datathread.stop ( )
    datathread.join ( )

    for m in meters_active :
        m.stop ( )
        m.join ( )

if __name__ == "__main__" :
    main ( )
