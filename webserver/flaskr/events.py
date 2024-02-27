from flask import Flask, request
from flask_socketio import SocketIO, emit, disconnect

socketio = SocketIO(cors_allowed_origins="*")

connected_clients = []

# TODO: Class for locker

@socketio.on("connect")
def handle_connect():
    connected_clients.append(request.sid)
    print(f"SocketIO connection established with sid: {request.sid}")
    
# TODO: Event for pi to authenticate and send locker info (setup)
    
@socketio.on("disconnect")
def handle_disconnect():
    connected_clients.remove(request.sid)
    print(f"SocketIO connection terminated with sid: {request.sid}")

# TODO: Event for pi to send status to server (possibly default message event)

# TODO: Method for finding sid based on locker info