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

from bokeh.plotting import figure, curdoc
from bokeh.driving import linear
from bokeh.models import DatetimeTickFormatter
from bokeh.models.widgets import Div,PreText
from bokeh.layouts import column,row
from bokeh.application.handlers.directory import DirectoryHandler

from bokeh.layouts import gridplot
from bokeh.models import CheckboxGroup
from bokeh.models import Slider
from bokeh.models import TextInput
from bokeh.models import DatePicker

from bokeh.models import Button

import random

import pandas as pd


import thermorasp
METERS = { "thermorasps": thermorasp }

global periodic_callback_id

def readout(meters):
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

    unixtime = int(time.time())
    return measurements

def store():
    time.sleep(10)
    measurements = readout(mymeters)
    for key,values in measurements.items():
        rasp = key.split('-')[0]
        sensor = key.replace('-','_')
        timestamp = [int(time.mktime(values[0].timetuple()))]
        measurement = {'temperature':[values[1]],'pressure':[values[2]],'humidity':[values[3]]}
        df = pd.DataFrame(data=measurement,index=timestamp)
#        print(df)
#        df.to_hdf('{}.h5'.format(rasp), key=sensor, format='table', append=True, complevel=5)
        df.to_hdf('/home/walsh/data/infrared-setup/{}.h5'.format(rasp), key=sensor, format='table', append=True)


@linear()
def update(step):
    measurements = readout(mymeters)
    # datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    
    for l in location:
        sdate = measurements[sensor[l]][0]
        for idx,key in enumerate(observables):
            meas = measurements[sensor[l]][idx+1]
            ds[l][key].data['x'].append(sdate)
            ds[l][key].data['y'].append(meas)
            ds[l][key].trigger('data', ds[l][key].data, ds[l][key].data)
        
            deltaT = (ds[l][key].data['x'][-1] - ds[l][key].data['x'][0]).seconds
            if deltaT > max_hours*3600:
                del ds[l][key].data['x'][0]
                del ds[l][key].data['y'][0]
    

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


def live_toggle(attr,old,new):
    global periodic_callback_id
#    datepicker_status()
    if len(new) == 1:
        reload_data()
        periodic_callback_id = curdoc().add_periodic_callback(update, 10000)
    else:
        curdoc().remove_periodic_callback(periodic_callback_id)
    
def datepicker_status(attr,old,new):
    date_picker_i.value = new
    live_checkbox.active = []
    print(date_picker_i.value,date_picker_f.value, live_checkbox.active)

def initial_date(attr,old,new):
    date_picker_i.value = new

def final_date(attr,old,new):
    date_picker_f.value = new

def get_history():

### FIX ME
#    global periodic_callback_id
    live_checkbox.active = []
#    curdoc().remove_periodic_callback(periodic_callback_id)
#    print(periodic_callback_id)
    sdata = {}
    sel_data = {}
    for l in location:
        sdata[sensor[l]] = pd.read_hdf('/home/walsh/data/infrared-setup/raspberryX.h5', sensor[l].replace('-','_'))
        last_ts = sdata[sensor[l]].iloc[-1].name
        first_ts = sdata[sensor[l]].iloc[0].name
        first_ts = last_ts-72*3600
        sel_data[l] = sdata[sensor[l]].loc[first_ts:last_ts]
        
        sdates = [datetime.fromtimestamp(ts) for ts in list(seldata[l].index)]
        for key in observables:
            ds[l][key].data = {'x':sdates, 'y':list(seldata[l][key])}
            ds[l][key].trigger('data', ds[l][key].data, ds[l][key].data)

def live_hours(attr,old,new):
    global max_hours
    try:
        max_hours = float(new)
    except:
        max_hours = float(old)
    if max_hours > 24:
        max_hours = 24
    if max_hours < 0.1:
        max_hours = 0.1
    live_hours_input.update(value=str(max_hours))
    reload_data()
        
def reload_data():
    seldata = readdata()
    for l in location:
        sdates = [datetime.fromtimestamp(ts) for ts in list(seldata[l].index)]
        for key in observables:
            ds[l][key].data = {'x':sdates, 'y':list(seldata[l][key])}
            ds[l][key].trigger('data', ds[l][key].data, ds[l][key].data)
    

def readdata():
    sdata = {}
    sel_data = {}
    for l in location:
        sdata[sensor[l]] = pd.read_hdf('/home/walsh/data/infrared-setup/raspberryX.h5', sensor[l].replace('-','_'))
        # remove possible duplicates (not sure why there are duplicates)
        sdata[sensor[l]] = sdata[sensor[l]].loc[~sdata[sensor[l]].index.duplicated(keep='first')]
        # reindex
        sdata[sensor[l]] = sdata[sensor[l]].sort_index()
        last_ts = sdata[sensor[l]].iloc[-1].name
        # get the nearest index
        first_idx = sdata[sensor[l]].index.get_loc(last_ts-max_hours*3600, method='nearest')
        # get the initial timestamp
        first_ts = sdata[sensor[l]].iloc[first_idx].name
        sel_data[l] = sdata[sensor[l]].loc[first_ts:last_ts]

#        sdates = [datetime.fromtimestamp(ts) for ts in list(sel_data.index)]
#        stemps = list(sel_data.temperature)
#        spress = list(sel_data.pressure)
#        shumts = list(sel_data.humidity)
    return sel_data

#def datei_changed(attr,old,new):


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
    
elif __name__.startswith('bokeh_app') or __name__.startswith('bk_script'):
    max_hours = 1

    # name starts with bk_script (__name__ = bk_script_<some number>)
    div = Div(text="<img src='cabinet-monitor/static/daf_25c_cabinet_sensors_test.jpg' width='300'>")
    plot = {}
    r = {}
    ds = {}
    color = {}
    sensor = {}
    colors = ['firebrick','navy','green']
    sensors = ['raspberry3-bus1-ch1','raspberry3-bus4-ch1','raspberry3-bus4-ch0']
    location = ['top','middle','bottom']
    observables = ['temperature','pressure','humidity']
    for i, l in enumerate(location):
        color[l] = colors[i]
        sensor[l] = sensors[i]
        r[l]  = {}
        ds[l] = {}
    plot[observables[0]] = figure(plot_width=500, plot_height=500,x_axis_type="datetime",toolbar_location="above")
    plot[observables[1]] = figure(plot_width=500, plot_height=500,x_axis_type="datetime",x_range=plot[observables[0]].x_range,toolbar_location="above")
    plot[observables[2]] = figure(plot_width=500, plot_height=500,x_axis_type="datetime",x_range=plot[observables[0]].x_range,toolbar_location="above")
    date_format = ['%d %b %Y %H:%M:%S']
    for key, p in plot.items():
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

        seldata = readdata()
        for l in location:
            sdates = [datetime.fromtimestamp(ts) for ts in list(seldata[l].index)]
#            r[l][key] = p.line([], [], color=color[l], line_width=2,legend_label=l)
#            r[l][key] = p.line(sdates, list(seldata[l][key]), color=color[l], line_width=2,legend_label=l)
            r[l][key] = p.circle(sdates, list(seldata[l][key]), fill_color=color[l], line_color=color[l], size=4,legend_label=l)
            ds[l][key] = r[l][key].data_source
        p.legend.location = "top_left"

        
    plot['temperature'].yaxis.axis_label = "Temperature (C)"
    plot['pressure'].yaxis.axis_label = "Pressure (hPa)"
    plot['humidity'].yaxis.axis_label = "Relative Humidity (%RH)"
    

    live_checkbox = CheckboxGroup(labels=['Live'], active=[0], width=150)
    live_checkbox.on_change('active',live_toggle)
    
    live_hours_input = TextInput(value=str(max_hours), title="Live past hours (max. 24h):", width=150)
    live_hours_input.on_change('value',live_hours)
    
#    live_slider = Slider(start=0.01, end=24, value=max_hours, step=0.01, title="Hours before")
#    live_slider.on_change('value',live_hours)
    
    # pick a date
    date_picker_i = DatePicker(value=date.today(),max_date=date.today(), title='Choose inital date:', width=150, disabled=False)
    mydate_i=date_picker_i.value
    date_picker_f = DatePicker(value=date.today(),max_date=date.today(), title='Choose final date:' , width=150, disabled=False)
    mydate_f=date_picker_f.value
    date_picker_i.on_change('value',initial_date)
    date_picker_f.on_change('value',final_date)
    
    hist_button = Button(label="Show History", button_type="default", width=310)
    hist_button.on_click(get_history)
    
    pre_head = PreText(text="N.B.: Readout every 10 seconds. Be patient!",width=500, height=50)
    pre_head2 = PreText(text="",width=400, height=25)
    pre_temp_top = PreText(text="",width=400, height=20)
    pre_temp_mid = PreText(text="",width=400, height=20)
    pre_temp_bot = PreText(text="",width=400, height=20)
    
    h_space = PreText(text="",width=50, height=1)
    v_space = PreText(text="",width=1, height=50)
    
#    curdoc().add_root(column(pre_head,row(div,column(pre_head2,pre_temp_top,pre_temp_mid,pre_temp_bot),column(plot['temperature'],plot['humidity'],plot['pressure']),)))
    curdoc().add_root(column(row(h_space,pre_head),row(h_space,live_hours_input, h_space, h_space, date_picker_i, date_picker_f), row(h_space,live_checkbox,h_space, h_space, hist_button),v_space,row(h_space,plot['temperature'],h_space,plot['humidity'],h_space,plot['pressure']), v_space,row(h_space,div)))
    
    readdata()
    main()
#    time.sleep ( 10 )
    periodic_callback_id = curdoc().add_periodic_callback(update, 10000)
else:
    pass    
