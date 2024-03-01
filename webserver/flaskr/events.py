from flask import Flask, request

from flask_socketio import SocketIO, emit, disconnect, send

from flaskr.sqlite_db import get_db

# TODO: Use .env or something similar to handle this
SECRET = "dev"

socketio = SocketIO(cors_allowed_origins="*")

# class LockerSpace:
#     pass

class Locker:
    # locker_list: LockerSpace = []
    
    def __init__(
        self,
        client_sid: str,
        id: int = None,
        num_lockers: int = 2
    ) -> None:
        self.client_sid = client_sid
        self.num_lockers = num_lockers
        self.id = id
    
    def __str__(self) -> str:
        return f"ID: {self.id} <-> SID: {self.client_sid}"

connected_clients: "list[Locker]" = []

################
# UTIL FUNCTIONS
################

def resolve_sid(sid: str) -> Locker:
    '''
    Takes an SID and finds the corresponding Locker object
    '''
    for client in connected_clients:
        if client.client_sid == sid:
            return client
    return None

################
# EVENT HANDLERS
################

@socketio.on("connect")
def handle_connect():
    new_locker = Locker(request.sid)
    connected_clients.append(new_locker)
    print(f"SocketIO connection established with sid: {request.sid}")

@socketio.on("init")
def handle_init(json):
    '''
    Client sends:
    {
        "auth"          : "<INSERT SECRET HERE>",
        "id"            : "3", 
        "num_lockers"   : "2"
    }
    '''
    
    db = get_db()
    locker = resolve_sid(request.sid)
    
    # Check for auth
    if not ("auth" in json):
        print(f"SID: {request.sid} - Sent no auth")
        disconnect()
        return
    if json["auth"] != SECRET:
        print(f"SID: {request.sid} - Sent incorrect auth")
        disconnect()
        return
    
    # Check for number of lockers
    if not ("num_lockers" in json):
        print(f"SID: {request.sid} - Sent no num_locker")
        disconnect()
        return
    locker.num_lockers = json["num_lockers"]
    
    # Check for ID
    if not ("id" in json):
        # Create new locker entry in database
        cursor = db.cursor()
        cursor.execute(f"INSERT INTO LOCKER (L_ON) VALUES (1)")
        new_id = cursor.lastrowid
        
        locker.id = new_id
    else:
        locker.id = json["id"]
        db.execute(f"UPDATE LOCKER SET L_ON = 1 WHERE ID = {locker.id}")
    db.commit()
    
    print(f"SID: {request.sid}, LID: {locker.id} - Locker initialized")
    send(f"{locker.id}")
    
@socketio.on("disconnect")
def handle_disconnect():
    db = get_db()
    
    locker = resolve_sid(request.sid)
    if not (locker.id is None):
        db.execute(f"UPDATE LOCKER SET L_ON = 0 WHERE ID = {locker.id}")
        print(f"LID: {locker.id} - turned off")
    
    connected_clients.remove(resolve_sid(request.sid))
    print(f"SocketIO connection terminated with SID: {request.sid}")

# TODO: Event for pi to send status to server (possibly default message event)

# TODO: Method for finding sid based on locker info