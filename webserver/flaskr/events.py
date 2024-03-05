from flask import Flask, request

from flask_socketio import SocketIO, emit, disconnect, send

from flaskr.sqlite_db import get_db

from datetime import datetime

# TODO: Use .env or something similar to handle this
SECRET = "dev"

STATUS_RATE = 300
'''Rate the server expects status updates in seconds'''

socketio = SocketIO(cors_allowed_origins="*")

class LockerSpace:
    def __init__(
        self
    ) -> None:
        
        self.reserver_id: int = None
        self.last_res_time: datetime = None
        
        self.status: dict = None
        self.last_stat_time: datetime = None
        # TODO: some sort of check for if status has been sent within status rate
    
    def reserve(self, user_id: int) -> bool:
        '''
        Assigns this locker space to the ID of the user passed
        Returns true if the locker was reserved, false otherwise
        '''
        current_datetime = datetime.now()
        
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
        
        # TODO: Finish
        # current_datetime = datetime.now()
        # self.last_status
    
    def __str__(self) -> str:
        return f"ID: {self.id} <-> SID: {self.client_sid}"
    
    def init_lockers(self, num_lockers: int):
        '''
        Initializes the list of LockerSpaces in this Locker
        '''
        self.locker_list = []
        
        for i in range(num_lockers):
            new_locker_space = LockerSpace()
            self.locker_list.append(new_locker_space)
            
            # TODO: Send unreserve command

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
    "init"
    {
        "id"            : "3",
        "status_rate"   : 300 # IN SECONDS
    }
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
    emit("init", {
        "id" : locker.id,
        "status_rate" : STATUS_RATE
    })
    
@socketio.on("disconnect")
def handle_disconnect():
    # db = get_db()
    
    # locker = resolve_sid(request.sid)
    # if not (locker.id is None):
    #     db.execute(f"UPDATE LOCKER SET L_ON = 0 WHERE ID = {locker.id}")
    #     print(f"LID: {locker.id} - turned off")
    
    connected_clients.remove(resolve_sid(request.sid))
    print(f"SocketIO connection terminated with SID: {request.sid}")

@socketio.on("json")
def handle_json(json):
    '''
    This will be the format of a standard status update from the client
    ```
    {
        "status_code"   : 0,        
        # 0 - OK
        # 1 - non-fatal error, device is still on 
        # 2 - fatal error, device has shut down
        "error_msg"     : "OK"      # Only needed if status is not 0
        "locker_list"   : [
            <DICT GOES HERE>,
            <DICT GOES HERE>
        ]
    }
    ```
    The server will send no response
    '''
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
    print(f"SID: {request.sid}, LID: {locker.id} - Recieved Status: {status_code}, Message: {msg}")
        
    # Handle locker space number
    if len(locker_list) != len(locker.locker_list):
        locker.init_lockers(len(locker_list))
        print(f"SID: {request.sid}, LID: {locker.id} - Num of lockers set to {len(locker_list)}")
        
    # Handle locker info
    current_datetime = datetime.now()
    for i in range(len(locker_list)):
        locker.locker_list[i].status = locker_list[i]
        locker.locker_list[i].last_stat_time = current_datetime

# TODO: Method for finding sid based on locker info