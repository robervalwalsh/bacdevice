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


import configparser
from sys import exit, version_info
import threading
import time
import pytz
from uuid import getnode

import csv
import sys
from datetime import datetime,timezone,date
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
import numpy as np

global periodic_callback_id

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

def initial_date(attr,old,new):
    date_picker_i.value = new

def final_date(attr,old,new):
    date_picker_f.value = new

def get_history():
    mydate_i=date_picker_i.value
    mydate_f=date_picker_f.value
    idate = datetime.strptime(mydate_i+' 00:00:00', '%Y-%m-%d %H:%M:%S')
    fdate = datetime.strptime(mydate_f+' 23:59:59', '%Y-%m-%d %H:%M:%S')
    its = int((idate - datetime(1970, 1, 1)).total_seconds())
    fts = int((fdate - datetime(1970, 1, 1)).total_seconds())
    sel_data = {}
    ## FIXME: force date range, if nearest too old then "remove" data 
    for l in location:
        if 'pt100' in l or 'ds18b20' in l:
            continue
        last_idx = alldata[l].index.get_loc(fts, method='nearest')
        last_ts = alldata[l].iloc[last_idx].name
        first_idx = alldata[l].index.get_loc(its, method='nearest')
        first_ts = alldata[l].iloc[first_idx].name
        
        for key in observables:
            r[l][key].visible = True
            
#        if last_ts-first_ts < 1 or l == 'left-top':
        if last_ts-first_ts < 1:
            sel_data[l] = alldata[l][0:0]
            for key in observables:
                r[l][key].visible = False
        else:
            sel_data[l] = alldata[l].loc[first_ts:last_ts]
            
        if first_ts < its:
            sel_data[l] = sel_data[l][1:]
        if last_ts > fts:
            sel_data[l] = sel_data[l][:-1]
        
        sdates = [datetime.fromtimestamp(ts) for ts in list(sel_data[l].index)]
        for key in observables:
            ds[l][key].data = {'x':sdates, 'y':list(sel_data[l][key])}
            ds[l][key].trigger('data', ds[l][key].data, ds[l][key].data)
            
            
    ## pt100 or single temp measurement 
    for l in location:
        if not 'pt100' in l and not 'ds18b20' in l:
            continue
        last_idx = alldata[l].index.get_loc(fts, method='nearest')
        last_ts = alldata[l].iloc[last_idx].name
        first_idx = alldata[l].index.get_loc(its, method='nearest')
        first_ts = alldata[l].iloc[first_idx].name
        
        r_pt100[l]['temperature'].visible = True
            
#        if last_ts-first_ts < 1 or l == 'left-top':
        if last_ts-first_ts < 1:
            sel_data[l] = alldata[l][0:0]
            r_pt100[l]['temperature'].visible = False
        else:
            sel_data[l] = alldata[l].loc[first_ts:last_ts]
            
        if first_ts < its:
            sel_data[l] = sel_data[l][1:]
        if last_ts > fts:
            sel_data[l] = sel_data[l][:-1]
        
        sdates = [datetime.fromtimestamp(ts) for ts in list(sel_data[l].index)]
        ds_pt100[l]['temperature'].data = {'x':sdates, 'y':list(sel_data[l]['temperature'])}
        ds_pt100[l]['temperature'].trigger('data', ds_pt100[l]['temperature'].data, ds_pt100[l]['temperature'].data)
            
    
    

def initialdata():
    # FIXME: check if alldata is available, otherwise readdata
    sel_data = {}
    now_ts = int(time.time())
    midnight_ts = int(time.mktime(datetime(datetime.today().year,datetime.today().month,datetime.today().day,tzinfo=timezone.utc).timetuple()))
    for l in location:
        last_idx = alldata[l].index.get_loc(now_ts, method='nearest')
        last_ts = alldata[l].iloc[last_idx].name
        # get the nearest index to midnight
        first_idx = alldata[l].index.get_loc(midnight_ts, method='nearest')
        # get the first timestamp
        first_ts = alldata[l].iloc[first_idx].name
#        if last_ts <= midnight_ts or l == 'left-top':
        if last_ts <= midnight_ts:
            sel_data[l] = alldata[l][0:0]
        else:
            # get selected data
            sel_data[l] = alldata[l].loc[first_ts:last_ts]
            
    return sel_data
        

@linear()
def update(step):
    readdata()

def readdata():
    sdata = {}
    sel_data = {}
    for l in location:
        mycsv = '{0}/{1}.csv'.format(directory,sensor[l])
        if l == 'outside':
            mycsv = '/home/walsh/data/desy-weather/{0}.csv'.format(sensor[l])
        if not path.exists(mycsv):
            continue
        
        
        if not 'pt100' in sensor[l] and not 'ds18b20' in sensor[l]:
            sdata[sensor[l]] = pd.read_csv(mycsv,names=("datetime","temperature","pressure","humidity"),parse_dates=[0],infer_datetime_format=True,comment='#',header=0)
        else:
            sdata[sensor[l]] = pd.read_csv(mycsv,names=("datetime","temperature"),parse_dates=[0],infer_datetime_format=True,comment='#',header=0)
            
        if l == 'outside':
            sdata[sensor[l]]['datetime'] = sdata[sensor[l]].datetime.dt.tz_localize('Europe/Berlin')
        else:
            sdata[sensor[l]]['datetime'] = sdata[sensor[l]].datetime.dt.tz_localize('UTC')
        # select only every n-th row: skip rows
        skip = 1
        if l == 'outside':
           skip = 1
        sdata[sensor[l]] = sdata[sensor[l]].iloc[::skip, :]
        # convert datetime to unix timestamp (FIXME: check timezone)
        sdata[sensor[l]]["timestamp"] = pd.DatetimeIndex ( sdata[sensor[l]]["datetime"] ).astype ( np.int64 )/1000000000
        sdata[sensor[l]]["timestamp"] = sdata[sensor[l]]["timestamp"].astype(int)
        sdata[sensor[l]].set_index("timestamp",inplace=True)
        
        # remove possible duplicates (not sure why there are duplicates)
        sdata[sensor[l]] = sdata[sensor[l]].loc[~sdata[sensor[l]].index.duplicated(keep='first')]
        # reindex
        sdata[sensor[l]] = sdata[sensor[l]].sort_index()
        
        if not 'pt100' in sensor[l] and not 'ds18b20' in sensor[l]:
            sdata[sensor[l]]["dewpoint"] = dew_point(sdata[sensor[l]]["temperature"],sdata[sensor[l]]["humidity"])
 
        sel_data[l] = sdata[sensor[l]]
               
    return sel_data


def main () :
    print('This is a bokeh server application')

### GLOBAL ###

if __name__ == "__main__" :
    main ()
    
elif __name__.startswith('bokeh_app') or __name__.startswith('bk_script'):
    date_format = ['%d %b %Y %H:%M:%S']
    # name starts with bk_script (__name__ = bk_script_<some number>)
    
    # read data from the files
    directory = '/home/walsh/data/infrared-setup'

    plot = {}
    r = {}
    ds = {}
    color = {}
    sensor = {}
    # FIX ME! Need more colors
    colors = ['firebrick','navy','green','lightblue','magenta','lightgreen','red','blue','black','gray']
#    sensors = ['raspberry7_bus1_ch1','raspberry7_bus4_ch1','raspberry7_bus6_ch1','raspberry7_bus5_ch1','raspberry8_bus5_ch1','raspberry8_bus6_ch1','raspberry8_bus4_ch1','raspberry8_bus1_ch1','raspberry9_bus1_ch1','krykWeather']
#    location = ['sensor #1','sensor #2','sensor #3','sensor #4','sensor #5','sensor #6','sensor #7','sensor #8','ref sensor']
    location = ['centre-bottom','right-bottom','right-middle','right-top','centre-top','left-top','left-middle','left-bottom','reference','outside']
    
    location.append('ds18b20_left-middle')
    location.append('ds18b20_centre-bottom')
#    location.append('pt100_3')
#    location.append('pt100_4')
    colors.append('magenta')
    colors.append('red')
#    colors.append('blue')
#    colors.append('green')
#    location = ['centre-bottom','right-bottom','right-middle','right-top','centre-top','left-top','left-middle','left-bottom','reference']
    sensors = []
    for l in location:
        if l == 'outside':
            sensors.append('krykWeather')
            continue
        if 'pt100' in l or 'ds18b20' in l:
            sensors.append('irsetup_'+l)
            continue
        sensors.append('irsetup_bme680_'+l)
        
    observables = ['dewpoint','temperature','pressure','humidity']
    for i, l in enumerate(location):
        color[l] = colors[i]
        sensor[l] = sensors[i]
        r[l]  = {}
        ds[l] = {}
        
    alldata = readdata()
    inidata = initialdata()
        
    plot[observables[0]] = figure(plot_width=500, plot_height=500,x_axis_type="datetime",toolbar_location="above")
    plot[observables[1]] = figure(plot_width=500, plot_height=500,x_axis_type="datetime",x_range=plot[observables[0]].x_range,toolbar_location="above")
    plot[observables[2]] = figure(plot_width=500, plot_height=500,x_axis_type="datetime",x_range=plot[observables[0]].x_range,toolbar_location="above")
    plot[observables[3]] = figure(plot_width=500, plot_height=500,x_axis_type="datetime",x_range=plot[observables[0]].x_range,toolbar_location="above")

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
        
        for l in location:
            if 'pt100' in l or 'ds18b20' in l:
                continue
            try:
                sdates = [datetime.fromtimestamp(ts) for ts in list(inidata[l].index)]
            except KeyError as e:
                continue
            #r[l][key] = p.line(sdates, list(inidata[l][key]), color=color[l], line_width=2,legend_label=l)
            r[l][key] = p.circle(sdates, list(inidata[l][key]), fill_color=color[l], line_color=color[l], size=3,legend_label=l)
            ds[l][key] = r[l][key].data_source
            if len(ds[l][key].data['x']) < 1:
                r[l][key].visible = False

        p.legend.location = "top_left"
        p.legend.orientation = "vertical"
        p.legend.click_policy="hide"
        
    plot['dewpoint'].yaxis.axis_label = "Dew Point (C)"
    plot['temperature'].yaxis.axis_label = "Temperature (C)"
    plot['pressure'].yaxis.axis_label = "Pressure (hPa)"
    plot['humidity'].yaxis.axis_label = "Relative Humidity (%RH)"
    
    ## pt100 plot

    plot_pt100 = {}
    plot_pt100['temperature'] =   figure(plot_width=500, plot_height=500,x_axis_type="datetime",x_range=plot['dewpoint'].x_range,toolbar_location="above")
    plot_pt100['temperature'].xaxis.formatter=DatetimeTickFormatter(
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
    plot_pt100['temperature'].xaxis.major_label_orientation = pi/3
    plot_pt100['temperature'].xaxis.axis_label = "Local time"
    r_pt100 = {}
    ds_pt100 = {}
    leg_pt100 = {}
    for l in location:
        if not 'pt100' in l and not 'ds18b20' in l:
            continue
        leg_pt100[l] = l
        r_pt100[l] = {}
        ds_pt100[l] = {}
        try:
            sdates = [datetime.fromtimestamp(ts) for ts in list(inidata[l].index)]
        except KeyError as e:
            continue
            
        r_pt100[l]['temperature'] = plot_pt100['temperature'].circle(sdates, list(inidata[l]['temperature']), fill_color=color[l], line_color=color[l], size=3,legend_label=leg_pt100[l])
        ds_pt100[l]['temperature'] = r_pt100[l]['temperature'].data_source
        if len(ds_pt100[l]['temperature'].data['x']) < 1:
            r_pt100[l]['temperature'].visible = False
            
    plot_pt100['temperature'].legend.location = "top_left"
    plot_pt100['temperature'].legend.orientation = "vertical"
    plot_pt100['temperature'].legend.click_policy="hide"
    plot_pt100['temperature'].yaxis.axis_label = "Temperature (C)"
    
              
    
    

#    sys.exit()
    
    # pick a date
    date_picker_i = DatePicker(value=date.today(),max_date=date.today(), title='Inital date:', width=150, disabled=False)
    mydate_i=date_picker_i.value
    date_picker_f = DatePicker(value=date.today(),max_date=date.today(), title='Final date:' , width=150, disabled=False)
    mydate_f=date_picker_f.value
    date_picker_i.on_change('value',initial_date)
    date_picker_f.on_change('value',final_date)

    hist_button = Button(label="Plot date selection", button_type="default", width=310)
    hist_button.on_click(get_history)
    
    
    pre_head = PreText(text="N.B.: A wide date range may take a long time to plot. Be patient!",width=500, height=50)
    pre_head2 = PreText(text="",width=400, height=25)
    pre_temp_top = PreText(text="",width=400, height=20)
    pre_temp_mid = PreText(text="",width=400, height=20)
    pre_temp_bot = PreText(text="",width=400, height=20)
    
    h_space = PreText(text="",width=50, height=1)
    v_space = PreText(text="",width=1, height=50)
    
    
    curdoc().add_root(column(row(h_space,pre_head),row(h_space, date_picker_i, date_picker_f), row(h_space, hist_button),v_space,row(h_space,plot['dewpoint'],h_space,plot_pt100['temperature']), v_space,row(h_space,plot['temperature'],h_space,plot['humidity']), v_space,row(h_space,plot['pressure'],h_space), v_space))
    
#    readdata()
#    main()
#    time.sleep ( 10 )
#    periodic_callback_id = curdoc().add_periodic_callback(update, 10000)
else:
    pass    
