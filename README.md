# BACDEVICE
* Based on [dustmeter](https://github.com/eyiliu/dustmeter).

* The setup will present a [BACNET](https://en.wikipedia.org/wiki/BACnet) device with a collection of [AnalogInputObjects](http://www.bacnet.org/Bibliography/ES-7-96/ES-7-96.htm).
* The AnalogInputObjects are the readout of various remote meters.

## Supported meters
* A [thermorasp](https://github.com/thomaseichhorn/fhlthermorasp) that runs the server.py
* A [pumpstation](https://github.com/Negusbuk/cmstkmodlab/tree/master/pumpstation) that runs the daemon
* A [DYLOS DC1700 air quality monitor](http://www.dylosproducts.com/dc1700.html) connected to a [USR-TCP232-302](http://www.usriot.com/user-manual-usr-tcp232-302-user-manual/) on TCP server mode listening at 8888 port

## Software dependencies:
* python 3.4 or newer
* [bacpypes](https://github.com/JoelBender/bacpypes) 0.16

### Install bacpypes
```
pip3 install bacpypes==0.16
```

## How to run
```
python3.4 main.py
```
Please make sure previous seesion of main.py have exited and relased the network port.

## How to configure
The configuration file is called server.cfg. It contains multiple \[sections\] of key = value pairs. Lines can be comments by prepending a #.

###Server section
The server section is the main configuration section. It has the following configuration keys:
* `ip`: IP address String
* `port`: Integer
* `objectName`: String
* `vendorIdentifier`: Integer
* `vendorName`: String
* `location`: String
* `modelName`: String
* `description`: String
* `dustmeters`: Optional, list of space seperated section names
* `thermorasps`: Optional, list of space seperated section names
* `pumpstations`: Optional, list of space seperated section names

The last three keys `dustmeters`, `thermorasps` and `pumpstations` have the value section names seperated by spaces.
Each of those section name corresponds to a configuration section of a meter to monitor.

###Meter sections
All meter configuration sections have the following optional keys:
* `description`: String
* `deviceType`: String
* `updateInterval`: Integer
* `resolution`: Float

###Dustmeter sections
A section that has been given in the value of the dustmeters key can have the following keys:
* `host`: String, defaults to `localhost`
* `port`: Integer, defaults to `8888`
* `name`: String, defaults to `dustMeter`
* `default_dust`: Defaults to `0`
* `reconnect`: Bool, defaults to `True`

###thermorasp sections
A section that has been given in the value of the thermorasps key can have the following keys:
* `host`: String, defaults to `localhost`
* `port`: Integer, defaults to `50007`
* `name`: String, defaults to `ThermoRasp`

###pumpstation sections
A section that has been given in the value of the pumpstations key can have the following keys:
* `host`: String, defaults to `localhost`
* `port`: Integer, defaults to `63432`
* `name`: String, defaults to `Pumpstation`
* `reconnect`: Bool, defaults to `False`


## Adding a new meter
To add support for another type of meter, create a new module with a new class, which inherits from `meter_base.MeterBase`.
The module must be imported in the `main.py` file and must be added as a value together with the configuration key it shall use to the METERS map in `main.py`.
The module needs to have a function called `getMeters`, that takes a map of configuration values, which was read from the configuration file, and returns a list of new meter objects.
The new class must implement `start` and `join` methods, which have the functionality of those of `threading.Thread`.
In addition the class has a `stop` method, which gets called when monitoring is supposed to be stopped, and a `getPresentValue` method to retrieve the current value.
