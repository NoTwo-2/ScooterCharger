import os

def find_temp_sensors():
    temp_sensors = []
    for i in os.listdir('/sys/bus/w1/devices'):
        if i != 'w1_bus_master1':
            temp_sensors.append(i)
    return temp_sensors
    
def read_temp(sensor_num):
    data = open('/sys/bus/w1/devices/' + sensor_num + '/w1_slave').read()
    temperature = float(data.split("=")[-1])
    return ((temperature / 1000) *1.8) + 32


def loop(ds18b20):
	while True:
		temp1 = read_temp(ds18b20)
		if temp1 != None:
			print("Current temperature: %0.3f F" % temp1)

def kill():
	quit()

if __name__ == '__main__':
	try:
		temp_sensors = find_temp_sensors()
