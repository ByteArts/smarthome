#!/usr/bin/env python

import serial.tools.list_ports

SER_TIMEOUT=0.3

"""
Enumerate available serial ports - returns a list of port names
"""
def GetSerialPortNames():
    pl = list(serial.tools.list_ports.comports())
    result = []

    for p in pl:
        result.append(p[0]) 

    return result
# end def GetSerialPortNames()



"""
Try to open a port with the specified baud rate.
Returns Serial object or None
"""
def OpenSerialPort(Portname, Baud):
    try:
        result = serial.Serial(Portname, baudrate=Baud, timeout=SER_TIMEOUT, writeTimeout=SER_TIMEOUT)
        result.flush()
        
    except serial.SerialException, err:
        result = None
        serr = str(err)
        # suppress the 'no such file' error
        if (serr.find('No such file') < 0):
            print 'OpenPort() failed: {0}'.format(serr)

    return result
# end def OpenSerialPort()

