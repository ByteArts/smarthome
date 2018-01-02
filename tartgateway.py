#!/usr/bin/env python

"""
tartgateway.py
This module is for monitoring data from a Tarts sensor gateway connected to a serial port.
Author: Scott Pinkham, ByteArts LLC
Date: Dec 29,2017
"""

#===IMPORTS===========================================================

import serial
import serial_utils
import time
import sys
from event import TEvent
from threading import Thread

#===CONSTANTS=========================================================

SENSOR_TYPE_TEMP = 2

GW_EVENT_JOIN = 0
GW_EVENT_SCAN = 1

#===CLASSES===========================================================


class TGatewayManager:
    def __init__(self):
        self.OnSensorData = TEvent()
        self.OnGatewayEvent = TEvent()
        self.SensorList = []
        self.GatewayID = '?'
        self._port = None
        self._thread = None
        self._stop = False
        

    def Find(self, ports):
        return FindGateway(ports)


    def _MonitorGateway(self, port):
        # <TODO: check that port is valid and is open>
        port.write('\r')
        port.flushInput()
        time.sleep(1)
        port.write('at$id\r') # request ID
        time.sleep(1)
        port.write('at$wl\r') # request list of devices
        
        # loop, checking for data 
        print '\nMonitoring gateway data..'
        while not self._stop:
            response = port.readline().lower().strip()
            if (len(response) > 2): # ignore lines with no data
                #print 'Data recvd:{0}'.format(response),
                if (response.startswith('id:')): # gateway id
                    self.GatewayID = ParseGatewayID(response)
                    print 'GatewayID: {0}'.format(self.GatewayID)
                elif (response.startswith('wd:')): # sensor data report
                    data = ParseSensorData(response)
                    self.OnSensorData(data) # fire the event
                #end if
                elif (response.startswith('wl:')): # sensor list
                    self.SensorList.append(ParseDeviceList(response))
                    #print 'Sensor list: {0}'.format(self.SensorList)
                #end elif
                elif (response.startswith('wj:')): # sensor joined network
                    data = StrAfter('wj:', response)
                    #print 'Sensor {0} joined network'.format(data)
                    self.OnGatewayEvent(GW_EVENT_JOIN, data)
                #end elif
                elif (response.startswith('ws:')): # sensor scanned network
                    data = ParseScanData(response)
                    #print 'Sensor {0} scanned network, sensor is {1}'.format(data['id'], data['known'])
                    self.OnGatewayEvent(GW_EVENT_SCAN, data)
                #end elif
            #end if      
        #end while
    #end def _MonitorGateway        


    def StartMonitor(self, portname):
        # <TODO: make sure a thread isn't already running>
        if (self._thread <> None):
            return False
        else:
            self.SensorList = []
            self.GatewayID = '?'

            # try to open the port
            self._port = serial_utils.OpenSerialPort(portname, 9600)
            if (self._port == None):
                return False

            # start monitor in background thread
            self._stop = False
            self._thread = Thread(target=self._MonitorGateway, args=(self._port,))
            self._thread.start()
            return True
        #end else
    #end def StartMonitor()

    def StopMonitor(self):
        # <TODO: make sure thread is running>
        print 'stopping monitor..'

        # set flag to signal to thread to exit
        self._stop = True

        # wait for thread to complete
        self._thread.join()

        print 'thread complete'
        self._thread = None

        # close serial port
        if (self._port <> None):
            self._port.close()
            self._port = None
    #end def StopMonitor()

#end class TGatewayManager
        

#===METHODS===========================================================


#=====================================================================


def StrAfter(substr, valuestr):
    result = valuestr.split(substr)
    if (len(result) > 1):
        return result[1]
    else:
        return ''
#end def StrAfter()


#=====================================================================


def ParseDeviceList(Response):
    result = StrAfter('wl:', Response).strip().lower()
    return result
#end def ParseDeviceList()


#=====================================================================


def ParseGatewayID(Response):
    result = StrAfter('id:', Response).strip().lower()
    return result
#end def ParseGatewayID()


#=====================================================================


def ParseScanData(Response):
    result = {'id': '?', 'known':'?', 'type':'?'}
    
    # format is ws:<id>,<type>,<known>
    data = StrAfter('ws:', Response).strip().lower()
    fields = data.split(',')
    if (len(fields) >= 3):
        result['id'] = fields[0]
        result['type'] = fields[1]
        if (fields[2] == '1'):
            result['known'] = 'known'
        else:
            result['known'] = 'unknown'
    #endif

    return result
#end def ParseScanData()


#=====================================================================
"""
Parse the sensor data, Response is in the format 'wd: <id>,<type>,<rssi>,<voltage>,<state>,<data>
Returns a dictionary {time, id, type, rssi, vbatt, state, value}
"""
def ParseSensorData(Response):
    #result = {'time': datetime.datetime.now(), 'id':'?', 'type':'?', 'rssi':'?', 'vbatt':'?', 'state':'?', 'value':0}
    result = {'time': time.strftime('%y%m%d %H:%M:%S'), 'id':'?', 'type':'?', 'rssi':'?', 'vbatt':'?', 'state':'?', 'value':0}
    
    values = Response.split('wd:')
    if (len(values) > 1):
        datafields=values[1].strip().split(',')
        if (len(datafields) >= 6):
            result['id'] = datafields[0]
            result['type'] = datafields[1]
            result['rssi'] = datafields[2]
            result['vbatt'] = datafields[3]
            result['state'] = datafields[4]
            result['value'] = datafields[5]
            
            # convert data into sensor value, depends on sensor type
            if (result['type'] == str(SENSOR_TYPE_TEMP)):
                value = result['value']
                if (len(value) == 4):
                    try:
                        # temp data is in tenths of deg C, in big endian
                        lsb = int(value[0] + value[1], 16)
                        msb = int(value[2] + value[3], 16)
                        deg = (lsb + 256 * msb) / 10.0

                        # convert to F
                        deg = 9.0/5.0 * deg + 32
                        result['value'] = '{0}F'.format(deg)
                        
                    except:
                        result['value'] = '?'
                #end if
            #end if
        #end if
    #end if

    return result
#end def ParseSensorData()


#=====================================================================
"""
Iterates thru the list of serial ports checking for the presence of the Tarts
wireless gateway. Returns the name of the serial port where the gateway was found (if any).
"""
def FindGateway(SerialPorts):
    # try to open each port and check for presence of Tarts gateway
    result = ''
    
    print '\nSearching for gateway on serial ports:'
    for pn in SerialPorts:
        print '\tChecking {0}..'.format(pn)
        port = serial_utils.OpenSerialPort(pn, 9600)
        if (port == None):
            continue

        try:
            # port is open, try sending a command and checking for a response
            port.write('\rat$\r')
            time.sleep(0.5)
            response = port.read(size=64).lower().strip()
            #print 'response=' + response

            if (response.find('ok') <> -1):
                print 'gateway found'
                result = pn
                break
            else:
                print 'gateway NOT found'
                continue
            
        except serial.SerialException:
            port.close()
            port = None
            continue
        #end try..except
    #end for p..

    if (port == None):
        print 'Error: no gateway found'
    else:
        port.close()

    return result
#end def FindGateway()

#=====================================================================
"""
Loop forever checking for sensor data. SerPort = serial port (Serial object) that the gateway
is connected to.
"""
"""
def MonitorGateway(SerPort):
    SensorList = []
    GatewayID = '?'
    
    SerPort.write('\r')
    SerPort.flushInput()
    time.sleep(1)
    SerPort.write('at$id\r') # request ID
    time.sleep(1)
    SerPort.write('at$wl\r') # request list of devices
    
    # loop, checking for data
    print '\nMonitoring gateway data..'
    while True:
        response = SerPort.readline().lower().strip()
        if (len(response) > 2): # ignore lines with no data
            #print 'Data recvd:{0}'.format(response),
            if (response.startswith('id:')): # gateway id
                GatewayID = ParseGatewayID(response)
                print 'GatewayID: {0}'.format(GatewayID)
            elif (response.startswith('wd:')): # sensor data report
                data = ParseSensorData(response)
                print 'Sensor Data: Time={0} ID={1} Value={2} RSSI={3} Vbat={4}'.format( \
                data['time'], data['id'], data['value'], data['rssi'], data['vbatt'])
            #end if
            elif (response.startswith('wl:')): # sensor list
                SensorList.append(ParseDeviceList(response))
                print 'Sensor list: {0}'.format(SensorList)
            #end elif
            elif (response.startswith('wj:')): # sensor joined network
                data = StrAfter('wj:', response)
                print 'Sensor {0} joined network'.format(data)
            #end elif
            elif (response.startswith('ws:')): # sensor scanned network
                data = ParseScanData(response)
                print 'Sensor {0} scanned network, sensor is {1}'.format(data['id'], data['known'])
            #end elif
        #end if      
    #end while
#end def MonitorGateway
"""

#===MAIN PROGRAM==================================================================

"""
Event handlers that are called when certain events occur on the gateway
"""

def GatewayEvent(kind, data):
    print 'GatewayEvent: kind={0} data={1}'.format(kind, data)
#end def GatewayEvent()


def SensorDataEvent(data):
    print 'SensorDataEvent: data={0}'.format(data)
#end def SensorDataEvent


"""
Check for serial ports, then look for the gateway and start monitoring data
"""

# get list of available serial ports
print 'Enumerating serial ports..',
aSerialPorts = serial_utils.GetSerialPortNames()
print '{0} serial port(s) found:'.format(len(aSerialPorts))
for p in aSerialPorts:
    print '\t{0}'.format(p)

if (len(aSerialPorts) < 1):
    print 'Error: no serial ports found'
    sys.exit(-1)
#end if

GatewayMgr = TGatewayManager()
portname = GatewayMgr.Find(aSerialPorts)
if (portname == ''):
    sys.exit(-2)

# assign event handlers
GatewayMgr.OnSensorData += SensorDataEvent
GatewayMgr.OnGatewayEvent += GatewayEvent

# start monitoring the gateway
print 'GatewayMgr running. Type "GatewayMgr.StopMonitor()" to stop'
GatewayMgr.StartMonitor(portname)

#while (True):
    # check for a keypress
    

#end
