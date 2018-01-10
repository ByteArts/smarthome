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
import threading

#===CONSTANTS=========================================================

SENSOR_TYPE_TEMP = 2

GW_EVENT_JOIN = 0
GW_EVENT_SCAN = 1

LOG_LEVEL = 0

#===CLASSES===========================================================

class TGatewayManager:
    """
    Class for managing communication with a Tarts wireless sensor gateway
    """
    def __init__(self):
        self.OnSensorData = TEvent()
        self.OnGatewayEvent = TEvent()
        self.SensorList = []
        self.GatewayID = '?'
        self._cmdlist = []
        self._cmdlistlock = threading.Lock()
        self._port = None
        self._thread = None
        self._stop = False


    def AddCommandToQueue(self, cmd):
        """
        Adds a command to the queue. Commands in the queue are sent while the monitor
        is running.
        """
        with self._cmdlistlock:
            self._cmdlist.append(cmd)
        

    def Find(self, ports):
        return FindGateway(ports)


    def _do_gateway_monitor(self, port):
        """
        Communicate with the gateway and monitor it for data. Runs in an infinite loop
        until _stop is False.
        """
        # <TODO: check that port is valid and is open>
        port.write('\r')
        time.sleep(0.5)
        port.write('at$\r')
        time.sleep(2)
        port.flushInput()

        with self._cmdlistlock:
            self._cmdlist.append('at$id\r')
            self._cmdlist.append('at$wl\r')
                
        # loop, checking for data 
        LogEntry(2, '\nMonitoring gateway data..')
        while not self._stop:
            # check for any commands that need to be sent
            if len(self._cmdlist) > 0:
                with self._cmdlistlock:
                    cmd = self._cmdlist[0]
                    LogEntry(2, 'Sending cmd: {0}'.format(cmd.strip()))
                    port.write(cmd)
                    del self._cmdlist[0]
                time.sleep(1)

            # check for data from gateway
            response = port.readline().lower().strip()
            
            if (len(response) > 2): # ignore lines with no data
                #print '\r\nData recvd:{0}'.format(response),
                if (response.startswith('id:')): # gateway id
                    self.GatewayID = ParseGatewayID(response)
                    LogEntry(2, 'GatewayID: {0}'.format(self.GatewayID))
                elif (response.startswith('wd:')): # sensor data report
                    data = ParseSensorData(response)
                    LogEntry(2, 'Sensor data: {0}'.format(data))
                    self.OnSensorData(data) # fire the event
                #end if
                elif (response.startswith('wl:')): # sensor list
                    self.SensorList.append(ParseDeviceList(response))
                    LogEntry(2, 'Sensor list: {0}'.format(self.SensorList))
                #end elif
                elif (response.startswith('wj:')): # sensor joined network
                    data = StrAfter('wj:', response)
                    LogEntry(2, 'Sensor {0} joined network'.format(data))
                    self.OnGatewayEvent(GW_EVENT_JOIN, data)
                #end elif
                elif (response.startswith('ws:')): # sensor scanned network
                    data = ParseScanData(response)
                    LogEntry(2, 'Sensor {0} scanned network, sensor is {1}'.format(data['id'], data['known']))
                    self.OnGatewayEvent(GW_EVENT_SCAN, data)
                #end elif
            #end if      
        #end while
    #end def _do_gateway_monitor        


    def Start(self, portname):
        """
        Opens the serial port and starts a thread to monitor for data from the gateway. It will also
        process the command queue and send commands from the queue out to the gateway.
        """
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
            self._thread = threading.Thread(target=self._do_gateway_monitor, args=(self._port,))
            self._thread.start()
            return True
        #end else
    #end def StartMonitor()


    def Stop(self):
        """
        """
        if (self._thread <> None):
            LogEntry(1, 'stopping monitor..')

            # set flag to signal to thread to exit
            self._stop = True

            # wait for thread to complete
            self._thread.join()

            LogEntry(1, 'thread complete')
            self._thread = None

        # close serial port
        if (self._port <> None):
            self._port.close()
            self._port = None
    #end def StopMonitor()

#end class TGatewayManager
        

#===METHODS===========================================================

def LogEntry(level, value):
    global LOG_LEVEL
    if level <= LOG_LEVEL:
        sys.stdout.write('gw:' + value + '\n') #SLog(value)
#end def LogEntry()    


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
    
    LogEntry(1, '\nSearching for gateway on serial ports:')
    for pn in SerialPorts:
        LogEntry(2, '\tChecking {0}..'.format(pn))
        port = serial_utils.OpenSerialPort(pn, 9600)
        if (port == None):
            continue

        try:
            # port is open, try sending a command and checking for a response
            port.write('\rat$\r')
            time.sleep(2)
            response = port.read(size=64).lower().strip()
            #print 'response=' + response

            if (response.find('ok') <> -1):
                LogEntry(1, 'gateway found')
                result = pn
                break
            else:
                LogEntry(2, 'gateway NOT found')
                continue
            
        except serial.SerialException:
            port.close()
            port = None
            continue
        #end try..except
    #end for p..

    if (port == None):
        LogEntry(1, 'Error: no gateway found')
    else:
        port.close()

    return result
#end def FindGateway()

#=====================================================================


#===MAIN PROGRAM==================================================================

"""
Event handlers that are called when certain events occur on the gateway
"""

def GatewayEvent(kind, data):
    LogEntry(1, 'GatewayEvent: kind={0} data={1}'.format(kind, data))
#end def GatewayEvent()


def SensorDataEvent(data):
    LogEntry(1, 'SensorDataEvent: data={0}'.format(data))
#end def SensorDataEvent


def StartGateway(on_data_event):
    """
    Check for serial ports, then look for the gateway and start monitoring data
    """
    
    # get list of available serial ports
    LogEntry(1, 'Enumerating serial ports..')
    ports = serial_utils.GetSerialPortNames()
    LogEntry(1, '{0} serial port(s) found:'.format(len(ports)))
    for p in ports:
        LogEntry(1, '\t{0}'.format(p))

    if (len(ports) < 1):
        LogEntry(0, 'Error: no serial ports found')
        return None
    #end if

    gateway = TGatewayManager()
    portname = gateway.Find(ports)
    if (portname == ''):
        return None

    # assign event handlers
    gateway.OnSensorData += on_data_event
    #gateway.OnGatewayEvent += GatewayEvent

    # start monitoring the gateway
    LogEntry(0, 'Starting gateway..')
    gateway.Start(portname)
    #print 'Gateway running. Type "Gateway.Stop()" to stop'
    return gateway
#end def StartGateway()

gw = None

def Test():
    global gw
    print 'Starting test..'
    gw = StartGateway(SensorDataEvent)
    print 'Type gw.Stop() to end'
#end
