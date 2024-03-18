import socketio
from datetime import datetime
import time

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
def lock(index):
    lockers[index]['state'] = "locked"
    sio.emit('json', {'status_code': 0, "locker_list": lockers})

@sio.on('unlock')
def unlock(index):
    lockers[index]['state'] = "unlocked"
    sio.emit('json', {'status_code': 0, "locker_list": lockers})
    
@sio.event
def disconnect():
    print("Disconnected from the server.")

def send_time_message():
    while True:
        # Get the current time
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Emit the message with the current time
        sio.emit('message', {'content': current_time})
        print(f"Sent time_message: {current_time}")
        
        # Wait for 10 seconds before sending the next message
        time.sleep(10)

if __name__ == '__main__':
    sio.connect(server_url)
    try:
        send_time_message()
    except KeyboardInterrupt:
        print("Client manually disconnected.")
        sio.disconnect()
