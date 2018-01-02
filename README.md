# smarthome
<p>
Collection of python scripts and other code for home automation. Currently in progress, working on temperature sensing using a Tarts wireless IoT gateway and wireless temperature sensors. To use this, you'll need a Tarts wireless gateway (available at <a href=http://TartsSensors.com>TartsSensors.com</a>) connected to a computer via a serial port, and one or more Tarts sensors (currently only the temperature sensor is supported, but it would be easy to add others).
</p>

<b>Platforms supported:</b>
<p>
I've only tested it on Raspberry Pi 3 running Raspian, but the Python code is totally portable and should work on any platform that supports Python 2.7 and serial ports.
</p>

<b>To use:</b>
<li>1. Connect the Tarts wireless gateway to the computer via a serial port. </li>
<li>2. Use a terminal program and the AT command set (see the Tarts documentation) to add your sensors to the gateway's network. (Eventually I will add the ability to manage sensors to the program, but I haven't gotten to that yet).</li>
<li>3. Run the tartgateway.py script -- it will search all the available serial ports looking for a gateway. Once it finds the gateway, it will create a task in a background thread that continues to monitor the gateway and print out any data recieved from a sensor.</li>
&nbsp
<p>
That's it! You can easily modify the SensorDataEvent() function to change what happens when a sensor reading is recieved.
</p>
