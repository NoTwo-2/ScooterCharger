from flask import Flask, request

from flask_socketio import SocketIO, emit, disconnect, send

from flaskr.sqlite_db import get_db

from datetime import datetime, timedelta

from .notifs import notify

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
            new_locker.unlock()

class Locker:
    def __init__(
        self,
        parent_station: ChargingStation
    ) -> None:
        self.parent_station = parent_station
        
        self.is_reserved: bool = False
        self.res_locked: bool = False
        self.reserver_id: int = None
        self.reserve_duration: int = None # In minutes
        self.last_res_time: datetime = None
        
        self.status: dict = {"state" : "unlocked"}
    
    def get_index(self) -> int:
        '''
        Gets index of this object in the ChargingStations's locker_list
        '''
        return self.parent_station.locker_list.index(self)
    
    def get_res_end(self) -> datetime:
        '''
        Returns datetime object containing when the reservation ends
        Returns None if there is no current reservation
        '''
        if not self.is_reserved:
            return None
        return self.last_res_time + timedelta(minutes=self.reserve_duration)
    
    def get_res_time_remaining(self) -> int:
        '''
        Returns (in seconds) how much time is remaining on the current reservation
        Returns None if there is no current reservation
        '''
        if not self.is_reserved:
            return None
        now = datetime.now()
        return (self.get_res_end() - now).total_seconds()
    
    def reserve(self, user_id: int, reserve_duration: int) -> bool:
        '''
        Assigns this locker to the ID of the user passed
        Returns true if the locker was reserved, false otherwise
        '''
        if self.is_reserved:
            return False
        self.is_reserved = True
        self.reserver_id = user_id
        self.reserve_duration = reserve_duration
        self.last_res_time = datetime.now()
    
    def unreserve(self) -> None:
        '''
        Unassigns this locker space
        '''
        self.is_reserved = False
        self.reserver_id = None
        self.reserve_duration = None
        
        self.unlock()

        # TODO: notifications (should be done where this function is called from)
        # To provide more context as to why the locker was unreserved
    
    def lock(self) -> None:
        '''
        Sends a lock SocketIO event to the connected charging station.
        Changes res_locked to True
        '''
        self.res_locked = True
        socketio.emit("lock", {
            "index" : self.get_index()
        }, to=self.parent_station.client_sid)
        print(f"SERVER - Sent lock command to SID: {self.parent_station.client_sid}, LID: {self.parent_station.id}")
    
    def unlock(self) -> None:
        '''
        Sends an unlock SocketIO event to the connected charging station
        Changes res_locked to False
        '''
        self.res_locked = False
        socketio.emit("unlock", {
            "index" : self.get_index()
        }, to=self.parent_station.client_sid)
        print(f"SERVER - Sent unlock command to SID: {self.parent_station.client_sid}, LID: {self.parent_station.id}")

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

def handle_reservation(locker: Locker) -> None:
    '''
    Determines whether the current reservation on a locker is still valid.
    Sends notifications and terminates the reservation depending on time left
    '''
    # check for reservation
    if not locker.is_reserved:
        return
    current_datetime = datetime.now()
    elapsed_time = current_datetime - locker.last_res_time
    minutes_left = locker.reserve_duration - int(elapsed_time.seconds / 60)
    
    # TODO: Send notification to user if time is almost up
    db = get_db()
    user_email = db.execute(f"SELECT EMAIL FROM APPUSER WHERE rowid = {locker.reserver_id}").fetchone()
    body = "Your reservation is ending soon! Pick up your scooter: (Link to site)"

    if minutes_left >= STATUS_RATE/60 and minutes_left < (STATUS_RATE/60)*2:
        subject = "Locker reservation expires in less 10 minutes!"
        notify([user_email], subject, body) == "sent"

    elif minutes_left > 0 and minutes_left < STATUS_RATE/60:
        subject = "Locker reservation expires in less 5 minutes!"
        notify([user_email], subject, body)
    
    # terminate reservation
    if minutes_left <= 0:
        # TODO: Send notification of termination of reservation
        subject = "Locker reservation has expired!"
        body = "Your reservation has ended! Pick up your scooter: (Link to site)"
        notify([user_email], subject, body)

        locker.unreserve()

################
# EVENT HANDLERS
################

@socketio.on("connect")
def handle_connect():
    new_station = ChargingStation(request.sid)
    connected_clients.append(new_station)
    print(f"SocketIO connection established with sid: {request.sid}")

# TODO: handle id collisions and assignment edge cases
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
    # cancel reservations in db
    db = get_db()
    charging_station = resolve_sid(request.sid)
    for locker in charging_station.locker_list:
        if not locker.is_reserved:
            continue
        db.execute(
            f"UPDATE APPUSER "
            f"SET RESERVED_CS_ID = NULL, "
            f"RESERVED_CS_SPACE_I = NULL "
            f"WHERE rowid = {locker.reserver_id}"
        )
        db.commit()

        # notify user
        user_email = db.execute(f"SELECT EMAIL FROM APPUSER WHERE rowid = {locker.reserver_id}").fetchone()
        subject = "Locker reservation ended!"
        body = "Your reservation has ended! Pick up your scooter: (Link to site)"
        notify([user_email], subject, body)

    # remove from connected clients
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
        handle_reservation(locker)
    
    print(charging_station)