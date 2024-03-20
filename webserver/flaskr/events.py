from flask import Flask, request

from flask_socketio import SocketIO, emit, disconnect, send

from flaskr.sqlite_db import get_db

from datetime import datetime

# TODO: Use .env or something similar to handle this
SECRET = "dev"

STATUS_RATE = 300
'''Rate the server expects status updates in seconds'''

socketio = SocketIO(cors_allowed_origins="*")

################
# HELPER CLASSES
################

class ChargingStation:
    locker_list: "list[Locker]" = []
    
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
        for locker in self.locker_list:
            string += f"- Reserved: {locker.is_reserved}, Last Reserved: {locker.last_res_time}, Status: {locker.status}\n"
        return string
    
    def init_lockers(self, num_lockers: int):
        '''
        Initializes the list of Lockers in this ChargingStation
        '''
        self.locker_list = []
        
        for _ in range(num_lockers):
            new_locker = Locker(self)
            self.locker_list.append(new_locker)
            
            new_locker.unreserve()

class Locker:
    def __init__(
        self,
        parent_station: ChargingStation
    ) -> None:
        self.parent_station = parent_station
        
        self.is_reserved: bool = False
        self.reserve_duration: int = None # In minutes
        self.last_res_time: datetime = None
        
        self.status: dict = {"state" : "unlocked"}
    
    def get_index(self) -> int:
        '''
        Gets index of this object in the ChargingStations's locker_list
        '''
        return self.parent_station.locker_list.index(self)
    
    def reserve(self, reserve_duration: int) -> bool:
        '''
        Assigns this locker to the ID of the user passed
        Returns true if the locker was reserved, false otherwise
        '''
        if not self.is_reserved or self.status["state"] != "unlocked":
            return False
        self.is_reserved = True
        self.reserve_duration = reserve_duration
        self.last_res_time = datetime.now()
        
        socketio.emit("lock", {
            "index" : self.get_index()
        }, to=self.parent_station.client_sid)
        print(f"SERVER - Sent lock command to SID: {self.parent_station.client_sid}, LID: {self.parent_station.id}")
    
    def unreserve(self) -> None:
        '''
        Unassigns this locker space
        '''
        self.is_reserved = False
        self.reserve_duration = None
        
        socketio.emit("unlock", {
            "index" : self.get_index()
        }, to=self.parent_station.client_sid)
        print(f"SERVER - Sent unlock command to SID: {self.parent_station.client_sid}, LID: {self.parent_station.id}")
        
        # TODO: notifications (should be done where this function is called from)
        # To provide more context as to why the locker was unreserved
    
    # TODO: Add lock and unlock methods and move emits to those methods

connected_clients: "list[ChargingStation]" = []

################
# UTIL FUNCTIONS
################

def resolve_sid(sid: str) -> ChargingStation:
    '''
    Takes an SID and finds the corresponding Charging Station object
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
    new_station = ChargingStation(request.sid)
    connected_clients.append(new_station)
    print(f"SocketIO connection established with sid: {request.sid}")

@socketio.on("init")
def handle_init(json):
    db = get_db()
    charging_station = resolve_sid(request.sid)
    
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
        cursor.execute(f"INSERT INTO CHARGING_STATION DEFAULT VALUES")
        new_id = cursor.lastrowid
        
        charging_station.id = new_id
    else:
        charging_station.id = json["id"]
        # db.execute(f"UPDATE LOCKER SET L_ON = 1 WHERE ID = {locker.id}")
    db.commit()
    
    print(f"SID: {request.sid}, CSID: {charging_station.id} - Charging station initialized")
    print(charging_station)
    socketio.emit("init", {
        "id" : charging_station.id,
        "status_rate" : STATUS_RATE
    })
    
@socketio.on("disconnect")
def handle_disconnect():
    connected_clients.remove(resolve_sid(request.sid))
    print(f"SocketIO connection terminated with SID: {request.sid}")

@socketio.on("json")
def handle_json(json):
    charging_station = resolve_sid(request.sid)
    if charging_station.id is None:
        print(f"SID: {request.sid} - Client has not initialized!")
        disconnect()
        return
    
    # Check for incorrect json
    if not ("status_code" in json) or not ("locker_list" in json):
        print(f"SID: {request.sid}, CSID: {charging_station.id} - Sent status update with missing information")
        return
    status_code = int(json["status_code"])
    locker_list: "list[dict]" = json["locker_list"]
    msg: str = "OK"
    
    if (status_code != 0):
        if not ("error_msg" in json):
            print(f"SID: {request.sid}, CSID: {charging_station.id} - Sent status update with error code and no error_msg")
            return
        msg = str(json["error_msg"])
    
    for locker in locker_list:
        if not ("state" in locker):
            print(f"SID: {request.sid}, CSID: {charging_station.id} - Sent locker_list in status update with missing information")
            return
    
    # TODO: Logging
    # TODO: Admin notifications
    current_datetime = datetime.now()
    charging_station.last_stat_time = current_datetime
    print(f"SID: {request.sid}, CSID: {charging_station.id} - Recieved status code: {status_code}, Message: '{msg}'")
        
    # Handle locker number
    if len(locker_list) != len(charging_station.locker_list):
        charging_station.init_lockers(len(locker_list))
        print(f"SID: {request.sid}, CSID: {charging_station.id} - Num of lockers set to {len(locker_list)}")
    
    # Handle locker info
    for i in range(len(locker_list)):
        locker = charging_station.locker_list[i]
        locker.status = locker_list[i]
    
    # TODO: check for expired reservation
    
    print(charging_station)

# TODO: remove this
@socketio.on("locked")
def handle_locked(json):
    charging_station = resolve_sid(request.sid)
    if charging_station.id is None:
        print(f"SID: {request.sid} - Client has not initialized!")
        disconnect()
        return
    
    # Check for incorrect json
    if not ("locker_i" in json):
        print(f"SID: {request.sid}, CSID: {charging_station.id} - Sent locked with missing information")
        return
    
    locker_i = int(json["locker_i"])
    locker = charging_station.locker_list[locker_i]
    
    # Set all relevant reservation member variables
    current_datetime = datetime.now()
    locker.is_reserved = True
    locker.last_res_time = current_datetime
    print(f"SID: {request.sid}, CSID: {charging_station.id} - Locked locker {locker}")

# TODO: remove this
@socketio.on("unlocked")
def handle_unlocked(json):
    charging_station = resolve_sid(request.sid)
    if charging_station.id is None:
        print(f"SID: {request.sid} - Client has not initialized!")
        disconnect()
        return
    
    # Check for incorrect json
    if not ("locker_i" in json):
        print(f"SID: {request.sid}, LID: {charging_station.id} - Sent unocked with missing information")
        return
    
    locker_i= int(json["locker_i"])
    locker = charging_station.locker_list[locker_i]
    
    # Set all relecant unreservation member variables
    locker.is_reserved = False
    locker.reserve_duration = None
    
    print(f"SID: {request.sid}, CSID: {charging_station.id} - Unocked locker {locker_i}")