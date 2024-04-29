from flask import Flask, request

from flask_socketio import SocketIO, emit, disconnect, send

from flaskr.sqlite_db import get_db

from datetime import datetime, timedelta

from .notifs import notify

# TODO: Use .env or something similar to handle this
SECRET = "dev"

STATUS_RATE = 300 # in seconds
'''Rate the server expects status updates in seconds'''
TIME_BEFORE_NOTIF = 240 # in minutes
'''Time before the server reminds the user to retrieve their items in minutes'''

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
        self.pending_reservations: list[tuple[int, int]] = []
        '''Formatted like [(user_id, locker_index), ...]'''
    
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
        Initializes the list of Lockers in this ChargingStation and applies any database reservations to the corresponding lockers
        '''
        self.locker_list = []
        
        # Populate locker list with new Lockers
        for _ in range(num_lockers):
            new_locker = Locker(self)
            self.locker_list.append(new_locker)
        debug(f"CSID: {self.id} - Num of lockers set to {num_lockers}")
        
        # Get list of database reservations for this charging station
        db = get_db()
        reses = db.execute(f"SELECT rowid, RESERVED_CS_SPACE_I FROM APPUSER WHERE RESERVED_CS_ID = {self.id}").fetchall()
        debug(f"CSID: {self.id} - Found {len(reses)} database reservations for this station")
        
        # Loop through list of current reservatons and apply them
        for res in reses:
            user_id = res["rowid"]
            locker_i = int(res["RESERVED_CS_SPACE_I"])
            if locker_i >= num_lockers:
                db.execute(
                    f"UPDATE APPUSER "
                    f"SET RESERVED_CS_ID = NULL, "
                    f"RESERVED_CS_SPACE_I = NULL "
                    f"WHERE rowid = {user_id}"
                )
                db.commit()
                debug(f"CSID: {self.id} - User {user_id} requested to reserve invalid locker {locker_i}")
                continue
            self.locker_list[locker_i].reserve(user_id)

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
    
    def get_elapsed_res_time(self) -> tuple[int, int, int]:
        '''
        Returns the elapsed reservation time as a tuple with the format (hours, minutes, seconds)
        '''
        if not self.is_reserved:
            return 0,0,0
        current_datetime = datetime.now()
        elapsed_time = current_datetime - self.last_res_time
        elapsed_hours = int(elapsed_time.seconds / 3600)
        elapsed_minutes = int((elapsed_time.seconds % 3600) / 60)
        elapsed_seconds = elapsed_time.seconds % 60
        return elapsed_hours, elapsed_minutes, elapsed_seconds
    
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
        
        # Send confirmation email
        user_email = get_user_email(user_id)
        subject = "Locker reservation confirmation"
        body = (
            f"Your reservation for locker number {self.get_index()} is now active! " 
            f"You may now open your locker and manage your reservation here: (link to site)\n\n" # TODO: add link
            f"Please be sure to retrieve your items and terminate your reservation when finished. "
            f"You will be sent a reminder email in {TIME_BEFORE_NOTIF} minutes."
        )
        notify([user_email], subject, body)
        
        debug(f"CSID: {self.parent_station.id} - User {user_id} reserved locker {self.get_index()}")
    
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
                    f"Your active reservation for locker number {self.get_index()} has been terminated for this reason: {reason}.\n"
                    f"If you still have items remaining inside the locker, "
                    f"you will have to re-reserve and open the locker at the website here (link to site)\n" # TODO: add link
                    f"If you are unable to retrieve your items, please contact StuCo immediatley."
                )
                notify([user_email], subject, body)
        debug(f"CSID: {self.parent_station.id} - User {self.reserver_id} unreserved locker {self.get_index()}")
        
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
        debug(f"SERVER - Sent unlock command to CSID: {self.parent_station.id}, LID: {self.get_index()}")

connected_clients: "list[ChargingStation]" = []

################
# UTIL FUNCTIONS
################

def debug(msg: str):
    message = f"[{datetime.now().strftime('%d/%b/%Y %H:%M:%S')}] "
    message += msg
    print(message)

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
    return db.execute(f"SELECT EMAIL FROM APPUSER WHERE rowid = {uid}").fetchone()[0]

def handle_reservation(locker: Locker) -> None:
    '''
    Determines whether the current reservation on a locker is still valid.
    Sends notifications and terminates the reservation depending on time left
    '''
    # check for reservation
    if not locker.is_reserved:
        return
    elapsed_hours, elapsed_minutes, elapsed_seconds = locker.get_elapsed_res_time()

    if elapsed_minutes > TIME_BEFORE_NOTIF:
        user_email = get_user_email(locker.reserver_id)
        subject = "Outstanding scooter locker reservation requires attention!"
        body = (
            f"You have held your current reservation for {elapsed_hours} hours, {elapsed_minutes} minutes, and {elapsed_seconds}.\n"
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
        debug(f"SID: {request.sid} - No ID given, assigned CSID: {rowid}")
        return rowid
    
    # Case: An ID is given but no db entry exists - Action: Create new entry with this ID and return the ID
    charging_station = db.execute(f"SELECT * FROM CHARGING_STATION WHERE CS_ID = {id}").fetchone()
    if charging_station is None:
        cursor = db.cursor()
        cursor.execute(f"INSERT INTO CHARGING_STATION(CS_ID, CS_LAST_UPDATE) VALUES ({id}, '{current_datetime}')")
        db.commit()
        debug(f"SID: {request.sid} - ID of {id} given, new DB entry created, assigned CSID: {id}")
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
        debug(f"SID: {request.sid} - ID of {id} given but DB entry already in use, new DB entry created, assigned CSID: {rowid}")
        return rowid
    
    # Case: An ID is given, there is a db entry, and there is no live connection using this entry - Action: return id
    # PYLANCE IS WRONG WHEN IT SAYS THIS CODE IS UNREACHABLE - IT VERY MUCH IS!
    debug(f"SID: {request.sid} - ID of {id} given, assigned CSID: {id}")
    return id

################
# EVENT HANDLERS
################

@socketio.on("connect")
def handle_connect():
    new_station = ChargingStation(request.sid)
    connected_clients.append(new_station)
    debug(f"SocketIO connection established with SID: {request.sid}")

@socketio.on("init")
def handle_init(json):
    charging_station = resolve_sid(request.sid)
    
    # Check for auth
    if not ("auth" in json):
        debug(f"SID: {request.sid} - Sent no auth")
        disconnect()
        return
    if json["auth"] != SECRET:
        debug(f"SID: {request.sid} - Sent incorrect auth")
        disconnect()
        return
    
    id = None if not ("id" in json.keys()) else json["id"]
    charging_station.id = handle_new_connection(id)
    
    debug(f"CSID: {charging_station.id} - Charging station initialized")
    socketio.emit("init", {
        "id" : charging_station.id,
        "status_rate" : STATUS_RATE
    })
    
@socketio.on("disconnect")
def handle_disconnect():
    charging_station = resolve_sid(request.sid)
    
    # Notify all users who have an active reservation 
    for locker in charging_station.locker_list:
        if not locker.is_reserved:
            continue
        user_email = get_user_email(locker.reserver_id)
        subject = "IMPORTANT - Reserved locker has been disconnected from the server"
        body = (
            f"Your activley reserved locker number {locker.get_index()} has been disabled due to being disconnected from the server.\n"
            f"While your locker remains disabled, you will not be unable to unlock the locker door via the website. "
            f"Your reservation will remain active, and normal operation will resume once the station is reconnected to the server.\n\n"
            f"You will receive an email when the station is re-connected and access to your locker is re-instated.\n"
            f"If you have any questions, please contact StuCo."
        )
        notify([user_email], subject, body)
        
    # remove from connected clients
    connected_clients.remove(charging_station)
    debug(f"SocketIO connection terminated with SID: {request.sid}")

@socketio.on("json")
def handle_json(json):
    current_datetime = datetime.now()
    db = get_db()
    charging_station = resolve_sid(request.sid)
    if charging_station.id is None:
        debug(f"SID: {request.sid} - Client has not initialized!")
        disconnect()
        return
    
    # Check for incorrect json
    if not ("status_code" in json) or not ("locker_list" in json):
        debug(f"CSID: {charging_station.id} - Sent status update with missing information")
        return
    status_code = int(json["status_code"])
    locker_list: "list[dict]" = json["locker_list"]
    msg: str = "OK"
    
    if (status_code != 0):
        if not ("error_msg" in json):
            debug(f"CSID: {charging_station.id} - Sent status update with error code and no error_msg")
            return
        msg = str(json["error_msg"])
    
    for locker in locker_list:
        if not ("state" in locker):
            debug(f"CSID: {charging_station.id} - Sent locker_list in status update with missing information")
            return
    
    # TODO: Admin notifications
    # Update last time updated
    charging_station.last_stat_time = current_datetime
    db.execute(
        f"UPDATE CHARGING_STATION "
        f"SET CS_LAST_UPDATE = '{current_datetime}' "
        f"WHERE CS_ID = {charging_station.id}"
    )
    db.commit()
    debug(f"CSID: {charging_station.id} - Recieved status code: {status_code}, Message: '{msg}'")
        
    # Handle locker number
    if len(locker_list) != len(charging_station.locker_list):
        charging_station.init_lockers(len(locker_list))
    
    # Handle locker info
    for i in range(len(locker_list)):
        locker = charging_station.locker_list[i]
        locker.status = locker_list[i]
        
        # Check for expired reservation
        handle_reservation(locker)
        
        # Check for non-good state
        if locker.status["state"] != "good":
            debug(f"CSID: {charging_station.id} - Locker {locker.get_index()} has been disabled, reservations terminated")
            # NOTE: Should we do this?
            if locker.is_reserved:
                user_email = get_user_email(locker.reserver_id)
                subject = "IMPORTANT - Reserved locker has been disabled due to unsafe operating conditions"
                body = (
                    f"Your activley reserved locker number {locker.get_index()} has been disabled due to unsafe operating conditions.\n"
                    f"While your locker remains disabled, you will not be unable to unlock the locker door via the website. "
                    f"Your reservation will remain active, and normal functionality will resume once operating conditions return to normal.\n\n"
                    f"Please periodically check your reservation here: (link to site)\n" # TODO: add link
                    f"If you have any questions, please contact StuCo."
                )
                notify([user_email], subject, body)
    
    #print(charging_station)