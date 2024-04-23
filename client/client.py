import socketio
from datetime import datetime
import time, os
import RPi.GPIO as GPIO
import serial, string
from config import server_url, locker_num, id, lock_pin, outlet_pin, max_curr, max_temp

@sio.event
def connect():
    if id is None:
        sio.emit('init', {'auth': "dev"})
    else:
        sio.emit('init', {'auth': "dev", "id": id})
        
    print("Connected to the server attempting authentication.")

@sio.on('init')
def on_init(data):
    print(f"Server says: {data}")
    update_config(data['id'])
    # Write id to config.py no matter what.
    save_rate = int(data['status_rate'])
    global initialized
    initialized = True

@sio.on('unlock')
def unlock(data):
    locker_index = data['index']
    print(f"Unlocking locker {locker_index}")
    GPIO.output(locker[locker_index]["pins"][""], True)
    lockers[locker_index]['state'] = "unlocked"
    sio.emit('json', {'status_code': 0, "locker_list": lockers})
    time.wait(5)
    GPIO.output(locker[locker_index]["pins"]["outlet"], False)
    lockers[locker_index]['state'] = "locked"
    
@sio.event
def disconnect():
    print("Disconnected from the server.")

def update_config(x):
    id = x
    with open('config.py', 'r') as file:
        lines = file.readlines()

    new_lines = []
    for line in lines:
        if line.strip().startswith('id ='):
            new_lines.append(f'id = {x}\n')
        else:
            new_lines.append(line)

    with open('config.py', 'w') as file:
        file.writelines(new_lines)
        
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


def update_message():
    while True:
        # Get the current temperature
        lockers[0]["temperature"] = read_temp(locker[0]["pins"]["temp"])
        lockers[0]["current"] = str(lockers[0]["pins"]["curr"].readline())[2:-5]
        
        # If any values out of bounds shutdown
        for locker in lockers:
            if locker["temperature"] > max_temp or locker["curr"] > max_curr:
                # shut down here
                GPIO.output(locker[locker_index]["pins"]["outlet"], False)
                sio.emit('json', {'status_code': 1, "message": f'EMERGENCY {locker} : {locker["temperature"] > {max_temp} , {locker["current"]} {max_curr}', "locker_list": lockers})

        
        
        # Emit the message with the current time
        sio.emit('json', {'status_code': 0, "locker_list": lockers})
        print(f"Sent message: {lockers}")
        
        # Wait for 10 seconds before sending the next message
        time.sleep(save_rate)

if __name__ == '__main__':
    # Create a Socket.IO client
    sio = socketio.Client()
    initialized = False
    save_rate = 10
    
    # Setup for sensors
    temp_sensors = find_temp_sensors()
    
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(lock_pin,GPIO.OUT)
    GPIO.setup(outlet_pin, GPIO.OUT)
    
    # Set pins
    locker[0]["pins"]["temp"] = temp_sensors[0]
    locker[0]["pins"]["curr"] = serial.Serial('/dev/ttyACM0',9600,8,'N',1,timeout=1)
    locker[0]["pins"]["lock"] = 17
    locker[0]["pins"]["outlet"] = 27

    # TODO: Initialize this list according to how many IO devices are present (is there an automatic way to figure this out via code?)
    lockers = [{
        "state": "unlocked",
        "temperature": 0,
        "current": 0,
        "sensors":{
            "temp":0,
            "curr":0,
            "lock":0,
            "outlet":0}
    } for x in range(locker_num)]
    
    # Connect to server
    print(f"Attempting connection to {server_url}...")
    sio.connect(server_url)
    while not initialized:
       continue
    
    # Main task executions
    print("Finished initialization")
    try:
        update_message()
    except KeyboardInterrupt:
        print("Client manually disconnected.")
        sio.disconnect()
