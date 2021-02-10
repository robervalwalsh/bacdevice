#!/usr/bin/env python3

import os

from argparse import ArgumentParser
from argparse import HelpFormatter

import pandas as pd

from datetime import date, timedelta,datetime

app = 'ArchiveReader.jar'
points = ['Temp','PLuft','relF']

minutes = 5
deltaT = timedelta(minutes=minutes)
######

def combinedWeather(start,end,n):
  
  df = {}
  for pv in points:
    cmd = f'cd /home/walsh/daf-monitoring/bacdevice/desy-weather; /usr/bin/java -jar ArchiveReader.jar -pv krykWeather:{pv}_ai -start {start} -end {end} -method AVERAGE -count {n} -output txt -path /tmp ; cd -'
    os.system(cmd)
    name = '/tmp/krykWeather_'+pv+'_ai.txt'
    # remove first and last lines
    os.system(f"sed -i '1d' {name}")
    os.system(f"sed -i '$d' {name}")
    df[pv] = pd.read_csv(name,names=("datetime",pv),parse_dates=[0,1],infer_datetime_format=True,sep='\t')
    
  df_comb = df['Temp'].merge(df['PLuft'])
  df_comb = df_comb.merge(df['relF'])
  
#  print(df_comb)
  
  df_comb.to_csv('/home/walsh/data/desy-weather/krykWeather.csv', mode='a', header=False, index=False)
  
  
##########

df = pd.read_csv('/home/walsh/data/desy-weather/krykWeather.csv',names=("datetime","temperature","pressure","humidity"),parse_dates=[0],infer_datetime_format=True)

dt1 = df.iloc[-1]['datetime']
dt2 = datetime.today()
npoints = int((dt2-dt1).seconds/deltaT.seconds)+1

start = dt1.strftime('%Y-%m-%d-%H-%M-%S')
end = (dt1+timedelta(minutes=minutes*npoints)).strftime('%Y-%m-%d-%H-%M-%S')

combinedWeather(start,end,npoints)
