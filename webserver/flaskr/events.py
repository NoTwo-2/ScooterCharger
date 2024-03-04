from flask import Flask, request

from flask_socketio import SocketIO, emit, disconnect, send

from flaskr.sqlite_db import get_db

import datetime

# TODO: Use .env or something similar to handle this
SECRET = "dev"

socketio = SocketIO(cors_allowed_origins="*")

class LockerSpace:
    def __init__(
        self
    ) -> None:
        
        self.reserver_id: int = None
        self.last_res_time: datetime.datetime = None
    
    def reserve(self, user_id: int) -> bool:
        '''
        Assigns this locker space to the ID of the user passed
        Returns true if the locker was reserved, false otherwise
        '''
        current_datetime = datetime.datetime.utcnow()
        
        if not (self.reserver_id is None):
            return False
        self.reserver_id = user_id
        self.last_res_time = current_datetime
        # TODO: request locker status before officially assigning the locker (prevent race conditions)
        # TODO: emit reserve event
    
    def unreserve(self) -> None:
        '''
        Unassigns this locker space
        '''
        self.reserver_id = None

class Locker:
    locker_list: "list[LockerSpace]" = []
    
    def __init__(
        self,
        client_sid: str,
        id: int = None
    ) -> None:
        self.client_sid = client_sid
        self.id = id
    
    def __str__(self) -> str:
        return f"ID: {self.id} <-> SID: {self.client_sid}"
    
    def init_lockers(self, num_lockers: int):
        '''
        Initializes the list of LockerSpaces in this Locker
        '''
        for _ in range(num_lockers):
            new_locker_space = LockerSpace()
            self.locker_list.append(new_locker_space)

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

# TODO: Emit events to specific lockers

###############
# EVENT EMITERS
###############

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
    ```
    {
        "auth"          : "<INSERT SECRET HERE>",
        "id"            : "3", 
        "num_lockers"   : "2"
    }
    ```
    Server sends:
    ```
    <LOCKER ID HERE>
    ```
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
    locker.init_lockers(json["num_lockers"])
    
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