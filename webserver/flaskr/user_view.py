from flask import Flask, Blueprint, request, g, session, redirect, url_for, render_template, flash

from .events import connected_clients, Locker, ChargingStation
# from .auth import load_user
from sqlite3 import Connection
from flaskr.sqlite_db import get_db

bp = Blueprint('user_view', __name__)

# Place any user-accessible locker routes here

# User Landing Page (1)
# redirect to manage reservation if user has active reservation
#   else redirect to avaiolable lockers list
@bp.route('/home', methods=['GET'])
def home():
    # check for account
    if not g.user:
        return redirect('/auth/login')
    print("RES SPACE I USER: ", g.user["RESERVED_CS_SPACE_I"]) 
    reserved_space = g.user["RESERVED_CS_SPACE_I"]
    if reserved_space is None:
        return redirect('/view-charging-stations')
    return redirect('/manage-locker')

@bp.route('/view-charging-stations')
def view_charging_stations():
    # Fetch the list of Charging Stations from the database
    stations = []
    
    # get db data
    db = get_db()
    rows = db.execute(f"SELECT rowid, * FROM CHARGING_STATION").fetchall()
    
    # loop thru each connected client
    for cs in connected_clients:
        for row in rows:
            if cs.id != row["rowid"]:
                continue
            
            station = dict()
            for key in row.keys():
                if row[key] is None:
                    station[key] = "None"
                else:
                    station[key] = row[key]
                
            locker_avail = 0
            for locker in cs.locker_list:
                if not locker.is_reserved: locker_avail += 1
            station["locker_num"] = locker_avail
        
            stations.append(station)
            break
    
    return render_template('auth/view_chargingstations.html', charging_stations=stations) 

# Lockers Page (2)
# show charging stations with available lockers and location
@bp.route('/view-lockers')
def show_available_lockers():
    station_id = int(request.args.get('station_id'))
    # list of dictionaries (cs table + num_lockers)
    avail_lckr: "list[dict]" = []

    # get cs table data
    db = get_db()
    charging_station = db.execute(f"SELECT rowid, * FROM CHARGING_STATION WHERE rowid = {station_id}").fetchone()

    # get charging station object
    cs: ChargingStation = None
    for client in connected_clients:
        if client.id == station_id:
            cs = client
    
    if cs is None:
        return "Bad Request", 400
    
    # construct locker dicts
    for locker in cs.locker_list:
        if locker.is_reserved:
            continue
        lckr = {}
        lckr['locker_id'] = cs.locker_list.index(locker)
        avail_lckr.append(lckr)

    return render_template('auth/view_available.html', lockers=avail_lckr, station_name=charging_station["CS_NAME"], station_id=station_id) 

# Reservation Form Page (3)
# select a charging station and reserve locker
@bp.route('/reserve-locker', methods=['POST'])
def reserve_locker():
    # check for account
    if not g.user:
        return redirect('/auth/login')
    user_id = g.user["rowid"]

    match request.method:
        case 'POST':
            # check for existing reservation
            db = get_db()
            result = get_locker_reserved(db, user_id)
            print(result)
            if result is not None:
                return redirect('/manage-locker')
            cs_id = int(request.form["station_id"])
            locker_i = int(request.form["locker_id"])
            # find selected charging station object
            charger = None
            for client in connected_clients:
                if cs_id == client.id:
                    charger = client
                    break
            if not charger or not charger.locker_list:
                #TODO: FLASH error messages on redirect
                return redirect('/view-charging-stations')
            # find available locker
            lckr: Locker = charger.locker_list[locker_i]
            if lckr.is_reserved or (lckr.status["state"] != "unlocked"):
                return redirect('/view-charging-stations')
            # start reservation
            reserve_time = 120
            lckr.reserve(user_id, reserve_time)
            db = get_db()
            db.execute(
                f"UPDATE APPUSER "
                f"SET RESERVED_CS_ID = {cs_id}, "
                    f"RESERVED_CS_SPACE_I = {lckr.get_index()} "
                f"WHERE rowid = {user_id}"
            )
            db.commit()
            return redirect('/manage-locker')
        case _:
            return "Bad Request", 400


# Reservation Management Page (4)
# cancel reservation, lock/unlock locker
@bp.route('/manage-locker', methods=['GET', 'POST'])
def cancel_reservation():
    # check for account
    print("HIII")
    if not g.user:
        return redirect('/auth/login')
    user_id = g.user["rowid"]
    
    # check for active reservation
    db = get_db()
    result = get_locker_reserved(db, user_id)
    if result is None:
        return redirect(url_for("user_view.show_available_lockers")) #"No active reservation"
    cs_id, locker_i = result
    
    match request.method:
        case 'POST':
            # get action item
            action = request.form.get("action")
            
            # get locker
            lckr = None
            for cs in connected_clients:
                if cs_id != cs.id:
                    continue
                if locker_i >= len(cs.locker_list):
                    break
                lckr = cs.locker_list[locker_i]
            if not lckr:
                return redirect(url_for("user_view.show_available_lockers")) # "Could not find locker", 

            # Deal with action
            match action:
                case 'toggle-lock':
                    if lckr.res_locked:
                        lckr.unlock()
                    else:
                        lckr.lock()
                    return redirect('/manage-locker')
                case 'unreserve':
                    lckr.unreserve()
                    db = get_db()
                    db.execute(
                        f"UPDATE APPUSER "
                        f"SET RESERVED_CS_ID = NULL, "
                        f"RESERVED_CS_SPACE_I = NULL "
                        f"WHERE rowid = {user_id}"
                    )
                    db.commit()
                    return redirect('/home')
                case _:
                    return redirect('/home') # "Invalid action"
            
        case 'GET':
            # TODO: Display the actual status of the locker's state
            return render_template('auth/manage_locker.html')
        case _:
            return "Bad Request", 400

def get_locker_reserved(db: Connection, user_id: int) -> tuple[int, int]:
    '''
    Takes in a database and a user's ID and returns the station ID and the locker index.
    Returns None if the user has no locker reserved
    '''
    row = db.execute(f"SELECT rowid, * FROM APPUSER WHERE rowid = {user_id}").fetchone()
    cs_id = row["RESERVED_CS_ID"]
    locker_i = row["RESERVED_CS_SPACE_I"]
    
    if cs_id is None or locker_i is None:
        return None
    
    # convert to int
    cs_id = int(cs_id)
    locker_i = int(locker_i)
    
    return (cs_id, locker_i)