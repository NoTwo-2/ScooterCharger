from flask import Flask, request

from flask_socketio import SocketIO, emit, disconnect, send

from flaskr.sqlite_db import get_db

from datetime import datetime, timedelta

from .notifs import notify

# TODO: Use .env or something similar to handle this
SECRET = "dev"

STATUS_RATE = 300 # in seconds
TIME_BEFORE_NOTIF = 240 # in minutes
'''Rate the server expects status updates in seconds'''

socketio = SocketIO(cors_allowed_origins="*")

# TODO: Logging for all print functions, maybe 

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
        self.reserver_id: int = None
        self.last_res_time: datetime = None
        
        self.status: dict = {"state" : "good"}
    
    def get_index(self) -> int:
        '''
        Gets index of this object in the ChargingStations's locker_list
        '''
        return self.parent_station.locker_list.index(self)
    
    def get_elapsed_res_time(self) -> tuple[int, int]:
        '''
        Returns the elapsed reservation time as a tuple with the format (minutes, seconds)
        '''
        current_datetime = datetime.now()
        elapsed_time = current_datetime - self.last_res_time
        elapsed_minutes = int(elapsed_time.seconds / 60)
        elapsed_seconds = elapsed_time.seconds % 60
        return elapsed_minutes, elapsed_seconds
    
    def reserve(self, user_id: int) -> bool:
        '''
        Assigns this locker to the ID of the user passed
        Returns true if the locker was reserved, false otherwise
        '''
        if self.is_reserved:
            return False
        self.is_reserved = True
        self.reserver_id = user_id
        self.last_res_time = datetime.now()
        
        # Update DB
        db = get_db()
        db.execute(
            f"UPDATE APPUSER "
            f"SET RESERVED_CS_ID = {self.parent_station.id}, "
            f"RESERVED_CS_SPACE_I = {self.get_index()} "
            f"WHERE rowid = {user_id}"
        )
        db.commit()
    
    def unreserve(self, reason="User Requested") -> None:
        '''
        Unassigns this locker space
        '''
        if not (self.reserver_id is None):
            # Update DB
            db = get_db()
            db.execute(
                f"UPDATE APPUSER "
                f"SET RESERVED_CS_ID = NULL, "
                f"RESERVED_CS_SPACE_I = NULL "
                f"WHERE rowid = {self.reserver_id}"
            )
            db.commit()
            
            # Send email if the reservation wasn't terminated via user request
            if reason != "User Requested":
                user_email = get_user_email(self.reserver_id)
                subject = "Locker reservation terminated"
                body = (
                    f"Your active reservation of Locker {self.get_index()} has been terminated for this reason: {reason}.\n"
                    "If you still have items remaining inside the locker, you will have to re-reserve and open the locker at the website.\n"
                    "If you are unable to retrieve your items, please contact StuCo immediatley."
                )
                notify([user_email], subject, body)
        
        self.is_reserved = False
        self.reserver_id = None
    
    def unlock(self) -> None:
        '''
        Sends an unlock SocketIO event to the connected charging station
        Changes res_locked to False
        '''
        socketio.emit("unlock", {
            "index" : self.get_index()
        }, to=self.parent_station.client_sid)
        print(f"SERVER - Sent unlock command to CSID: {self.parent_station.id}, LID: {self.get_index()}")

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

def get_user_email(uid: int) -> str:
    '''
    Returns the email of the user with the given ID
    '''
    db = get_db()
    return db.execute(f"SELECT EMAIL FROM APPUSER WHERE rowid = {uid}").fetchone()

def handle_reservation(locker: Locker) -> None:
    '''
    Determines whether the current reservation on a locker is still valid.
    Sends notifications and terminates the reservation depending on time left
    '''
    # check for reservation
    if not locker.is_reserved:
        return
    elapsed_minutes, elapsed_seconds = locker.get_elapsed_res_time()

    if elapsed_minutes > TIME_BEFORE_NOTIF:
        user_email = get_user_email(locker.reserver_id)
        subject = "Outstanding scooter locker reservation requires attention!"
        body = (
            f"You have held your current reservation for {elapsed_minutes} minutes and {elapsed_seconds}.\n"
            f"Consider retrieving your items and terminating your reservation here: (Link to site)\n"
            f"This email will continue to be sent every {int(STATUS_RATE/60)} minutes until your reservation is terminated"
        )
        notify([user_email], subject, body)
        
def handle_new_connection(id: int = None) -> int:
    '''
    Takes in an ID and returns an ID to send back to the locker
    Does various actions depending on the situation
    '''
    current_datetime = datetime.now()
    db = get_db()
    
    # Case: No ID is given - Action: Create new entry and return auto-generated ID
    if id is None:
        cursor = db.cursor()
        cursor.execute(f"INSERT INTO CHARGING_STATION(CS_LAST_UPDATE) VALUES ('{current_datetime}')")
        rowid = cursor.lastrowid
        db.commit()
        print(f"  No ID given, assigned CSID: {rowid}")
        return rowid
    
    # Case: An ID is given but no db entry exists - Action: Create new entry with this ID and return the ID
    charging_station = db.execute(f"SELECT * FROM CHARGING_STATION WHERE CS_ID = {id}").fetchone()
    if charging_station is None:
        cursor = db.cursor()
        cursor.execute(f"INSERT INTO CHARGING_STATION(CS_ID, CS_LAST_UPDATE) VALUES ({id}, '{current_datetime}')")
        db.commit()
        print(f"  ID: {id} given, new DB entry created, assigned CSID: {id}")
        return id
    
    # Case: An ID is given, there is a db entry, but there is a live connection using this entry - Action: Create new entry and return auto-generated ID
    cs: ChargingStation = None
    for client in connected_clients:
        if client.id == id:
            cs = client
            break
    if not (cs is None):
        cursor = db.cursor()
        cursor.execute(f"INSERT INTO CHARGING_STATION(CS_LAST_UPDATE) VALUES ('{current_datetime}')")
        rowid = cursor.lastrowid
        db.commit()
        print(f"  ID: {id} given but DB entry already in use, new DB entry created, assigned CSID: {rowid}")
        return rowid
    
    # Case: An ID is given, there is a db entry, and there is no live connection using this entry - Action: return id
    # PYLANCE IS WRONG WHEN IT SAYS THIS CODE IS UNREACHABLE - IT VERY MUCH IS!
    print(f"  ID: {id} given, assigned CSID: {id}")
    return id

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
    
    print(f"SID: {request.sid} - Assigning locker ID...")
    id = None if not ("id" in json.keys()) else json["id"]
    charging_station.id = handle_new_connection(id)
    
    print(f"SID: {request.sid}, CSID: {charging_station.id} - Charging station initialized")
    socketio.emit("init", {
        "id" : charging_station.id,
        "status_rate" : STATUS_RATE
    })
    
@socketio.on("disconnect")
def handle_disconnect():
    charging_station = resolve_sid(request.sid)
    for locker in charging_station.locker_list:
        if locker.is_reserved:
            locker.unreserve(reason="Charging Station Has Shut Down")
        
    # remove from connected clients
    connected_clients.remove(charging_station)
    print(f"SocketIO connection terminated with SID: {request.sid}")

@socketio.on("json")
def handle_json(json):
    current_datetime = datetime.now()
    db = get_db()
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
    
    # TODO: Admin notifications
    charging_station.last_stat_time = current_datetime
    db.execute(
        f"UPDATE CHARGING_STATION "
        f"SET CS_LAST_UPDATE = '{current_datetime}' "
        f"WHERE CS_ID = {charging_station.id}"
    )
    db.commit()
    print(f"SID: {request.sid}, CSID: {charging_station.id} - Recieved status code: {status_code}, Message: '{msg}'")
        
    # Handle locker number
    if len(locker_list) != len(charging_station.locker_list):
        charging_station.init_lockers(len(locker_list))
        print(f"SID: {request.sid}, CSID: {charging_station.id} - Num of lockers set to {len(locker_list)}")
    
    # Handle locker info
    for i in range(len(locker_list)):
        locker = charging_station.locker_list[i]
        locker.status = locker_list[i]
        
        # Check for expired reservation
        handle_reservation(locker)
        
        # Check for non-good state
        if locker.status["state"] != "good":
            print(f"SID: {request.sid}, CSID: {charging_station.id} - Locker {locker.get_index()} has been disabled, reservations terminated")
            # TODO: Notify users of updated state
            if locker.is_reserved:
                user_email = get_user_email(locker.reserver_id)
                pass
    
    #print(charging_station)