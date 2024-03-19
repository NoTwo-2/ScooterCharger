import socketio
from datetime import datetime
import time, os

from config import server_url

# TODO: order IO devices so that they can be accessed via a locker index
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

# Create a Socket.IO client
sio = socketio.Client()

# TODO: Initialize this list according to how many IO devices are present (is there an automatic way to figure this out via code?)
lockers = [{"state": "unlocked", "temperature": 0, "current": 0}, {"state": "OFF", "temperature": 0, "current": 0}]
initialized = False

@sio.event
def connect():
    sio.emit('init', {'auth': "dev"})
    print("Connected to the server attempting authentication.")

@sio.on('init')
def on_init(data):
    print(f"Server says: {data}")
    save_id = data['id']
    save_rate = data['status_rate']
    global initialized
    initialized = True

@sio.on('lock')
def lock(data):
    locker_index = data['index']
    print(f"Locking locker {locker_index}")
    lockers[locker_index]['state'] = "locked"
    sio.emit('json', {'status_code': 0, "locker_list": lockers})

@sio.on('unlock')
def unlock(data):
    locker_index = data['index']
    print(f"Unlocking locker {locker_index}")
    lockers[locker_index]['state'] = "unlocked"
    sio.emit('json', {'status_code': 0, "locker_list": lockers})
    
@sio.event
def disconnect():
    print("Disconnected from the server.")

def send_time_message():
    while True:
        # Get the current temperature
        # cur_temp = read_temp(temp_sensors[0])
        # lockers[0]["temperature"] = cur_temp
        
        # Emit the message with the current time
        sio.emit('json', {'status_code': 0, "locker_list": lockers})
        print(f"Sent message: {lockers}")
        
        # Wait for 10 seconds before sending the next message
        time.sleep(10)

if __name__ == '__main__':
    # temp_sensors = find_temp_sensors()
    print(f"Attempting connection to {server_url}...")
    sio.connect(server_url)
    while not initialized:
        continue
    print("Finished initialization")
    try:
        send_time_message()
    except KeyboardInterrupt:
        print("Client manually disconnected.")
        sio.disconnect()
