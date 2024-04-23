#!/usr/bin/python
import serial, string

output =""
serial_input = serial.Serial('/dev/ttyACM0',9600,8,'N',1,timeout=1)
while True:
	print("----")
	while output !="":
		output=serial_input.readline()
		if("Current" in str(output)):
			print(output)
