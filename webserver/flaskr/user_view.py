from flask import Flask, Blueprint, request, g, session, redirect, url_for, render_template, flash

from .events import connected_clients, Locker, ChargingStation
# from .auth import load_user
from sqlite3 import Connection
from flaskr.sqlite_db import get_db
from datetime import datetime

bp = Blueprint('user_view', __name__)

# Place any user-accessible locker routes here

# User Landing Page (1)
# redirect to manage reservation if user has active reservation
#   else redirect to avaiolable lockers list
@bp.route('/home', methods=['GET'])
def home():
    reserved_space = g.user["RESERVED_CS_SPACE_I"]
    if reserved_space is None:
        return redirect('/view-charging-stations')
    return redirect('/manage-locker')

# Lockers Page (2)
# show charging stations with available lockers and location
@bp.route('/view-charging-stations')
def view_charging_stations():
    # Fetch the list of Charging Stations from the database
    online_stations = []
    offline_stations = []
    
    # get db data
    db = get_db()
    rows = db.execute(f"SELECT * FROM CHARGING_STATION").fetchall()
    
    admin = g.user["ACCESS_TYPE"] == "ADMIN"
    
    # loop thru each charging station in the db
    for row in rows:
        # transfer row data to new dict object
        station = dict()
        for key in row.keys():
            station[key] = row[key]
        
        cc = False
        # check for connected clients
        for cs in connected_clients:
            if cs.id != row["CS_ID"]:
                continue
            # matching connected client
            station["total_lockers"] = len(cs.locker_list)
            if not (cs.last_stat_time is None):
                station["update_time"] = cs.last_stat_time.strftime("%a, %d at %I:%M:%S %p")
            else:
                station["update_time"] = None
            locker_avail = 0
            lockers = []
            for lckr in cs.locker_list:
                if not lckr.is_reserved: locker_avail += 1
            
                locker = dict()
                locker["index"] = lckr.get_index()
                locker["status"] = lckr.status
                locker["reserved"] = lckr.is_reserved
                if lckr.is_reserved:
                    user_email = db.execute(f"SELECT EMAIL FROM APPUSER WHERE rowid = {lckr.reserver_id}").fetchone()[0]
                else:
                    user_email = None
                locker["user"] = user_email
                elapsed_hr, elapsed_min, elapsed_sec = lckr.get_elapsed_res_time()
                locker["elapsed_res"] = f"{elapsed_hr} hours, {elapsed_min} minutes, {elapsed_sec} seconds"
                locker["reserve_time"] = None if lckr.last_res_time is None else lckr.last_res_time.strftime("%a, %d at %I:%M:%S %p")
                
                lockers.append(locker)
            station["locker_num"] = locker_avail
            station["locker_list"] = lockers
            
            online_stations.append(station)
            cc = True
            break
        # no connected clients
        if not cc:
            offline_stations.append(station)
    
    return render_template(
        'auth/view_chargingstations.html', 
        charging_stations=online_stations,
        offline_stations=offline_stations, 
        admin=admin
    ) 

@bp.route('/view-lockers')
def show_available_lockers():
    station_id = request.args.get('station_id')
    if station_id is None:
        flash("Incomplete URL.","error")
        return redirect(url_for("user_view.view_charging_stations"))
    station_id = int(station_id)
    # list of dictionaries (cs table + num_lockers)
    avail_lckr: "list[dict]" = []

    # get cs table data
    db = get_db()
    charging_station = db.execute(f"SELECT * FROM CHARGING_STATION WHERE CS_ID = {station_id}").fetchone()

    # get charging station object
    cs: ChargingStation = None
    for client in connected_clients:
        if client.id == station_id:
            cs = client
    
    if cs is None:
        flash("The charging station associated with this locker is no longer connected to the server.","warning")
        return redirect(url_for("user_view.view_charging_stations"))
    
    # construct locker dicts
    for locker in cs.locker_list:
        if locker.is_reserved or locker.status["state"] != "good":
            continue
        lckr = {}
        lckr['locker_id'] = locker.get_index()
        avail_lckr.append(lckr)

    return render_template(
        'auth/view_available.html', 
        lockers=avail_lckr, 
        station_name=charging_station["CS_NAME"], 
        station_id=station_id
    ) 

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
            if not (result is None):
                flash("You already have an existing reservation!","warning")
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
                flash("Requested locker is no longer connected. Please try again.","warning")
                return redirect('/view-charging-stations')
            # find available locker
            lckr: Locker = charger.locker_list[locker_i]
            if lckr.is_reserved or (lckr.status["state"] != "good"):
                flash("Requested locker is no longer available. Please try again.","warning")
                return redirect('/view-charging-stations')
            # start reservation
            lckr.reserve(user_id)
            flash("Locker successfully reserved!","info")
            return redirect('/manage-locker')
        case _:
            flash("???")
            return redirect('/home') # "Invalid action"


# Reservation Management Page (4)
# cancel reservation, lock/unlock locker
@bp.route('/manage-locker', methods=['GET', 'POST'])
def manage_reservation():
    user_id = g.user["rowid"]
    
    # check for active reservation
    db = get_db()
    result = get_locker_reserved(db, user_id)
    if result is None:
        flash("No active reservation found.","warning")
        return redirect(url_for("user_view.view_charging_stations"))
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

            # Deal with action
            match action:
                case 'open':
                    if lckr.status["state"] != "good":
                        return "Bad Request", 400
                    lckr.unlock()
                    flash("Sent unlock command to locker.","info")
                    return redirect('/manage-locker')
                case 'unreserve':
                    if not lckr:
                        db.execute(
                            f"UPDATE APPUSER "
                            f"SET RESERVED_CS_ID = NULL, "
                            f"RESERVED_CS_SPACE_I = NULL "
                            f"WHERE rowid = {user_id}"
                        )
                        db.commit()
                    else:
                        lckr.unreserve()
                    flash("Successfully unreserved locker.","info")
                    return redirect('/home')
                case _:
                    flash("???")
                    return redirect('/home') # "Invalid action"
            
        case 'GET':
            charging_station = db.execute(f"SELECT * FROM CHARGING_STATION WHERE CS_ID = {cs_id}").fetchone()
            lckr: Locker = None
            for client in connected_clients:
                if client.id != cs_id:
                    continue
                for locker in client.locker_list:
                    if locker.get_index() == locker_i:
                        lckr = locker
            
            if lckr:
                elapsed_hours, elapsed_minutes, elapsed_seconds = lckr.get_elapsed_res_time()
                disabled = lckr.status["state"] != "good"
            else:
                elapsed_hours, elapsed_minutes, elapsed_seconds = 0,0,0
                disabled = True
            
            return render_template(
                'auth/manage_locker.html', 
                charging_station=charging_station, 
                locker_id=locker_i, 
                disabled=disabled, 
                elapsed_hours=elapsed_hours,
                elapsed_minutes=elapsed_minutes,
                elapsed_seconds=elapsed_seconds
            )
        case _:
            flash("???")
            return redirect('/home') # "Invalid action"

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

@bp.before_request
def filter_admin():
    '''
    Redirects if session user is not an admin
    '''
    if not g.user:
        flash("Please login or create an account.","warning")
        return redirect("/auth/login")