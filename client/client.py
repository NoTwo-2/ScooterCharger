import socketio
from datetime import datetime
import time, os

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

# Define the URL of the Socket.IO server
server_url = 'http://192.168.0.120:5000'  # Change this to your server's IP address and port

lockers = [{"state": "unlocked", "temperature": 0, "current": 0}, {"state": "OFF", "temperature": 0, "current": 0}]


@sio.event
def connect():
    sio.emit('init', {'auth': "dev"})
    print("Connected to the server attempting authentication.")

@sio.on('init')
def on_init(data):
    print(f"Server says: {data}")
    save_id = data['id']
    save_rate = data['status_rate']
    sio.emit('json', {'status_code': 0, "locker_list": lockers})

@sio.on('lock')
def lock(data):
    lockers[data['index']]['state'] = "locked"
    sio.emit('json', {'status_code': 0, "locker_list": lockers})

@sio.on('unlock')
def unlock(data):
    lockers[data['index']]['state'] = "unlocked"
    sio.emit('json', {'status_code': 0, "locker_list": lockers})
    
@sio.event
def disconnect():
    print("Disconnected from the server.")

def send_time_message():
    while True:
        # Get the current time
        cur_temp = read_temp(temp_sensors[0])
        lockers[0]["temperature"] = cur_temp
        
        # Emit the message with the current time
        sio.emit('json', {'status_code': 0, "locker_list": lockers})
        print(f"Sent time_message: {lockers}")
        
        # Wait for 10 seconds before sending the next message
        time.sleep(10)

if __name__ == '__main__':
    temp_sensors = find_temp_sensors()
    sio.connect(server_url)
    try:
        send_time_message()
    except KeyboardInterrupt:
        print("Client manually disconnected.")
        sio.disconnect()
