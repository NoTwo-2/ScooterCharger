from flask import Flask, request

from flask_socketio import SocketIO, emit, disconnect, send

from flaskr.sqlite_db import get_db

from datetime import datetime

# TODO: Use .env or something similar to handle this
SECRET = "dev"

STATUS_RATE = 300
'''Rate the server expects status updates in seconds'''

socketio = SocketIO(cors_allowed_origins="*")

class Locker:
    locker_list: "list[LockerSpace]" = []
    
    def __init__(
        self,
        client_sid: str,
        id: int = None
    ) -> None:
        self.client_sid = client_sid
        self.id = id
        
        self.last_stat_time: datetime = None
    
    def __str__(self) -> str:
        string = (
            f"ID: {self.id} <-> SID: {self.client_sid}\n" +
            f"Last status update: {self.last_stat_time}\n"
        )
        for locker_space in self.locker_list:
            reserved = not locker_space.reserver_id is None
            string += f"- Reserved: {reserved}, Last Reserved: {locker_space.last_res_time}, Status: {locker_space.status}\n"
        return string
    
    def init_lockers(self, num_lockers: int):
        '''
        Initializes the list of LockerSpaces in this Locker
        '''
        self.locker_list = []
        
        for _ in range(num_lockers):
            new_locker_space = LockerSpace(self)
            self.locker_list.append(new_locker_space)
            
            new_locker_space.unreserve()

class LockerSpace:
    def __init__(
        self,
        parent_locker: Locker
    ) -> None:
        self.parent_locker = parent_locker
        
        self.reserver_id: int = None
        self.reserve_duration: int = None # In minutes
        self.last_res_time: datetime = None
        
        self.status: dict = None
    
    def get_index(self) -> int:
        '''
        Gets index of this object in the Locker's locker_list
        '''
        return self.parent_locker.locker_list.index(self)
    
    def reserve(self, user_id: int, reserve_duration: int) -> bool:
        '''
        Assigns this locker space to the ID of the user passed
        Returns true if the locker was reserved, false otherwise
        '''
        current_datetime = datetime.now()
        
        if not (self.reserver_id is None):
            return False
        self.reserver_id = user_id
        self.reserve_duration = reserve_duration
        self.last_res_time = current_datetime
        
        emit("reserve", {
            "index" : self.get_index()
        }, to=self.parent_locker.client_sid)
    
    def unreserve(self) -> None:
        '''
        Unassigns this locker space
        '''
        emit("unreserve", {
            "index" : self.get_index()
        }, to=self.parent_locker.client_sid)
        
        self.reserver_id = None
        self.reserve_duration = None
        
        # TODO: notifications (should be done where this function is called from)
        # To provide more context as to why the locker was unreserved
    
    def is_reserved(self) -> bool:
        '''
        Returns True if this space is reserved, False otherwise
        '''
        return not self.reserver_id is None 

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
    
    # Check for ID
    if not ("id" in json):
        # Create new locker entry in database
        cursor = db.cursor()
        cursor.execute(f"INSERT INTO LOCKER DEFAULT VALUES")
        new_id = cursor.lastrowid
        
        locker.id = new_id
    else:
        locker.id = json["id"]
        # db.execute(f"UPDATE LOCKER SET L_ON = 1 WHERE ID = {locker.id}")
    db.commit()
    
    print(f"SID: {request.sid}, LID: {locker.id} - Locker initialized")
    print(locker)
    emit("init", {
        "id" : locker.id,
        "status_rate" : STATUS_RATE
    })
    
@socketio.on("disconnect")
def handle_disconnect():
    locker = resolve_sid(request)
    if not (locker.id is None):
        # Unreserve all locker spaces on disconnect
        for locker_space in locker.locker_list:
            locker_space.unreserve()
    
    connected_clients.remove(resolve_sid(request.sid))
    print(f"SocketIO connection terminated with SID: {request.sid}")

@socketio.on("json")
def handle_json(json):
    locker = resolve_sid(request.sid)
    if locker.id is None:
        print(f"SID: {request.sid} - Client has not initialized!")
        disconnect()
        return
    
    # Check for malformed json
    if not ("status_code" in json) or not ("locker_list" in json):
        print(f"SID: {request.sid}, LID: {locker.id} - Sent malformed status update")
        return
    status_code: int = json["status_code"]
    locker_list: "list[dict]" = json["locker_list"]
    msg: str = "OK"
    
    if (status_code != 0):
        if not ("error_msg" in json):
            print(f"SID: {request.sid}, LID: {locker.id} - Sent error code with no error_msg")
            return
        msg = json["error_msg"]
    
    # TODO: Logging
    # TODO: Admin notifications
    current_datetime = datetime.now()
    locker.last_stat_time = current_datetime
    print(f"SID: {request.sid}, LID: {locker.id} - Recieved Status: {status_code}, Message: {msg}")
        
    # Handle locker space number
    if len(locker_list) != len(locker.locker_list):
        locker.init_lockers(len(locker_list))
        print(f"SID: {request.sid}, LID: {locker.id} - Num of lockers set to {len(locker_list)}")
        
    # Handle locker info
    for i in range(len(locker_list)):
        locker.locker_list[i].status = locker_list[i]
    
    # TODO: check for expired reservation
    
    print(locker)