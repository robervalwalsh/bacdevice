#!/usr/bin/env python3

import os

from argparse import ArgumentParser
from argparse import HelpFormatter

import pandas as pd

from datetime import date, timedelta

app = 'ArchiveReader.jar'
points = ['Temp','PLuft','relF']

######

def combinedWeather(date1):
  
  # next day - needed to adjust to the ArchiveReader format
  date2 = date.isoformat(date.fromisoformat(date1) + timedelta(days=1))
  
  df = {}
  for pv in points:
    cmd = f'java -jar ArchiveReader.jar -pv krykWeather:{pv}_ai -start {date1}-00-00-00 -end {date2}-00-00-00 -method AVERAGE -count 288 -output txt'
    os.system(cmd)
    name = 'krykWeather_'+pv+'_ai.txt'
    newname = 'krykWeather_'+pv+f'_ai-{date1}.txt'
    # remove first and last lines
    os.system(f"sed -i '1d' {name}")
    os.system(f"sed -i '$d' {name}")
    df[pv] = pd.read_csv(name,names=("datetime",pv),parse_dates=[0,1],infer_datetime_format=True,sep='\t')
    
  df_comb = df['Temp'].merge(df['PLuft'])
  df_comb = df_comb.merge(df['relF'])
  
  df_comb.to_csv('/home/walsh/data/desy-weather/krykWeather.csv', mode='a', header=False, index=False)
  
  
##########


parser = ArgumentParser(prog='dailyWeather.py', formatter_class=lambda prog: HelpFormatter(prog,indent_increment=6,max_help_position=80,width=280), description='Prepare and submit jobs to NAF HTCondor batch system')
parser.add_argument("-d", "--date", dest="date", help="date in format YYYY-MM-DD")
args = parser.parse_args()

date1 = date.isoformat(date.today()-timedelta(days=1))
if args.date:
  date1 = args.date


date1 = '2020-12-22'

last_date = date.isoformat(date.today()-timedelta(days=1))

while date1 != last_date:
  combinedWeather(date1)
  date1 = date.isoformat(date.fromisoformat(date1) + timedelta(days=1))
