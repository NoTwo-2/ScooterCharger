import socketio
import time, os
import socketio.exceptions
from config import server_url, locker_num, id, max_curr, max_temp

try:
    import RPi.GPIO as GPIO
    import serial, string
    dummy_client = False
except ImportError:
    dummy_client = True

# Create a Socket.IO client
sio = socketio.Client()

###############
# EVENTS
###############

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
    new_l_list = json_lockers()
    sio.emit('json', {'status_code': 0, "locker_list": new_l_list})
    global save_rate
    save_rate = int(data['status_rate'])
    global initialized
    initialized = True

@sio.on('unlock')
def unlock(data):
    LOCK_SIGNAL_DURATION = 0.1
    locker_index = data['index']
    if lockers[locker_index]["pins"]["lock"] is None:
        return
    print(f"Unlocking locker {locker_index}")
    if not dummy_client:
        GPIO.output(lockers[locker_index]["pins"]["lock"], True)
    new_l_list = json_lockers()
    sio.emit('json', {'status_code': 0, "locker_list": new_l_list})
    time.sleep(LOCK_SIGNAL_DURATION)
    if not dummy_client:
        GPIO.output(lockers[locker_index]["pins"]["lock"], False)
    
@sio.event
def disconnect():
    print("Disconnected from the server.")
    initialized = False

###############
# UTIL
###############

def update_config(x):
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
    try:
        data = open('/sys/bus/w1/devices/' + str(sensor_num) + '/w1_slave').read()
    except FileNotFoundError:
        return 0
    temperature = float(data.split("=")[-1])
    return ((temperature / 1000) *1.8) + 32

def json_lockers(lockers: list[dict]):
    l_list = []
    for l in lockers:
        new_l = {}
        for key in l.keys():
            if key != "pins":
                new_l[key] = l[key]
        l_list.append(new_l)
    return l_list

def update_message():
    while True:
        # Loop periodically based on save_rate
        time.sleep(save_rate)
        # NOTE: shouldnt this be getting checked more frequently?
        # If any values out of bounds shutdown
        unsafe_temps = ""
        unsafe_currs = ""
        for locker in lockers:
            # Get the most recent sensor values
            if not dummy_client:
                if not locker["pins"]["temp"] is None:
                    locker["temperature"] = read_temp(locker["pins"]["temp"])
                if not locker["pins"]["curr"] is None:
                    locker["current"] = float(str(locker["pins"]["curr"].readline())[2:-5])
                
            unsafe_temp = locker["temperature"] > max_temp
            unsafe_current = locker["current"] > max_curr
            if (not unsafe_temp) and (not unsafe_current):
                if not dummy_client:
                    if not locker["pins"]["outlet"] is None:
                        GPIO.output(locker["pins"]["outlet"], True)
                locker["state"] = "good"
                continue
            
            # shut down here
            if not dummy_client:
                GPIO.output(locker["pins"]["outlet"], False)
            locker["state"] = "disabled"
            
            # append datas
            if unsafe_temp:
                unsafe_temps += f"ID: {lockers.index(locker)} - {locker['temperature']}\n"
            if unsafe_current:
                unsafe_currs += f"ID: {lockers.index(locker)} - {locker['current']}\n"
        
        # Emit the json event
        new_l_list = json_lockers(lockers)
        try:
            if unsafe_currs == "" and unsafe_temps == "":
                sio.emit('json', {'status_code': 0, "locker_list": new_l_list})
            else:
                final_message = (
                    f"One or more lockers were disabled due to unsafe conditions\n\n"
                    f"Lockers that exceeded a maximum safe temperature of {max_temp}:\n{unsafe_temps}\n"
                    f"Lockers that exceeded a maximum safe current of {max_curr}:\n{unsafe_currs}"
                )
                sio.emit('json', {'status_code': 1, "error_msg": final_message, "locker_list": new_l_list})
        except socketio.exceptions.BadNamespaceError:
            print(f"Attempted to emit JSON message, got BadNamespaceError")
        
        print(f"Sent JSON {new_l_list}")

###############
# INIT
###############

if __name__ == '__main__':
    initialized = False
    save_rate = 10

    # TODO: Initialize this list according to how many IO devices are present (is there an automatic way to figure this out via code?)
    lockers = [{
        "state": "good",
        "temperature": 0,
        "current": 0,
        "pins":{
            "temp":None,
            "curr":None,
            "lock":None,
            "outlet":None}
    } for x in range(locker_num)]
    
    if not dummy_client:
        # Setup for sensors
        temp_sensors = find_temp_sensors()
        #print(temp_sensors)
        #print(read_temp(temp_sensors[0]))
        
        # Set pins for each locker
        lockers[0]["pins"]["temp"] = temp_sensors[0]
        lockers[0]["pins"]["curr"] = serial.Serial('/dev/ttyACM0',9600,8,'N',1,timeout=1)
        lockers[0]["pins"]["lock"] = 17
        lockers[0]["pins"]["outlet"] = 27
        
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(lockers[0]["pins"]["lock"] ,GPIO.OUT) # NOTE: these are depricated, i dont know where they come from now?
        GPIO.setup(lockers[0]["pins"]["outlet"], GPIO.OUT)
        
    
    # Connect to server
    print(f"Attempting connection to {server_url}...")
    sio.connect(server_url, retry=True)
    while not initialized:
        continue
    
    # Main task executions
    print("Finished initialization")
    try:
        update_message()
    except KeyboardInterrupt:
        print("Client manually disconnected.")
        sio.disconnect()
