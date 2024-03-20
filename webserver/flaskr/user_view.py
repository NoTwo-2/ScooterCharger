from flask import Flask, Blueprint, request, g, session, redirect, url_for

from .events import connected_clients, Locker, ChargingStation
# from .auth import load_user
from flaskr.sqlite_db import get_db

bp = Blueprint('user_view', __name__)

# Place any user-accessible locker routes here
# None of these should return rendered templates

# User Landing Page (1)
# redirect to manage reservation if user has active reservation
#   else redirect to avaiolable lockers list
@bp.route('/home', methods=['GET'])
def home():
    # check for account
    if not g.user:
        return redirect('/auth/login')
    
    if not g.user["RESERVED_CS_SPACE_I"]:
        return redirect('/view-available')

    active_res = g.user["RESERVED_CS_SPACE_I"]
    return redirect('/manage-locker')


# Lockers Page (2)
# show charging stations with available lockers and location
@bp.route('/view-available')
def show_available_lockers():

    # list of dictionaries (cs table + num_lockers)
    avail_lckr: "list[dict]" = []

    # list of ChargingStation objects
    avail: "list[ChargingStation]" = []

    # add cs with available lockers to avail list with num_lockers
    for cs in connected_clients:
        avail.append(cs)

    # get cs table data
    db = get_db()
    records = db.execute(f"SELECT rowid, * FROM CHARGING_STATION").fetchall()

    # put location and num_locker into dictionary
    for cs in avail:
        for row in records:
            if cs.id != row[0]:
                continue
            
            for i in range(len(cs.locker_list)):
                locker = cs.locker_list[i]
                if locker.is_reserved:
                    continue
                # TODO: check if locker is under maintenence (state)
                
                avail_lckr.append({
                    "locker_id": i,
                    "cs_id": row[0],
                    "cs_name": row[1],
                    "cs_gmap_link": row[2],
                    "cs_address": row[3]
                })
            break

    return {"available_lockers" : avail_lckr}

# Reservation Form Page (3)
# select a charging station and reserve locker
@bp.route('/reserve-locker', methods=['POST'])
def reserve_locker():
    # check for account
    if not g.user:
        return redirect('/auth/login')
    user_id = g.user["ID"]

    match request.method:
        case 'POST':
            cs_id = int(request.form["station_id"])
            locker_i = int(request.form["locker_id"])
            
            # find selected charging station object
            charger = None
            for client in connected_clients:
                if cs_id == client.id:
                    charger = client
                    break

            if not charger or not charger.locker_list:
                return "Charging Station not found.", redirect('/view-available')

            # find available locker
            lckr: Locker = charger.locker_list[locker_i]
            if lckr.is_reserved or (lckr.status["state"] != "unlocked"):
                return "Locker is unavailable.", redirect('/view-available')
    
            # start reservation
            reserve_time = 120
            lckr.reserve(reserve_time)

            db = get_db()
            db.execute(
                f"UPDATE APPUSER "
                f"SET RESERVED_CS_ID = {cs_id}, "
                    f"RESERVED_CS_SPACE_I = {lckr.get_index()} "
                f"WHERE ID = {user_id}"
            )

            return redirect('/manage-locker')
        case _:
            return "Bad Request", 400


# Reservation Management Page (4)
# cancel reservation, lock/unlock locker
@bp.route('/manage-locker', methods=['GET', 'POST'])
def cancel_reservation():
    # check for account
    if not g.user:
        return redirect('/auth/login')
    user_id = g.user["ID"]
    
    match request.method:
        case 'POST':
            # check for reservation
            db = get_db()
            row = db.execute(f"SELECT rowid, * FROM APPUSER WHERE rowid = {user_id}").fetchone()
            cs_id = int(row["RESERVED_CS_ID"])
            locker_i = int(row["RESERVED_CS_SPACE_I"])
            
            if cs_id is None or locker_i is None:
                return "No active reservation", redirect(url_for("user_view.view-available"))
            
            lckr = None
            for cs in connected_clients:
                if cs_id != cs.id:
                    continue
                if locker_i >= len(cs.locker_list):
                    return "Locker index out of range", redirect(url_for("user_view.view-available"))
                lckr = cs.locker_list[locker_i]
            if not lckr:
                return "Could not find locker", redirect(url_for("user_view.view-available"))
    
            # end reservation
            lckr.unreserve()

            db = get_db()
            db.execute(
                f"UPDATE APPUSER "
                f"SET RESERVED_CS_ID = NULL, "
                    f"RESERVED_CS_SPACE_I = NULL "
            f"WHERE ID = {user_id}"
            )

            return redirect('/home')
        case _:
            return "Bad Request", 400

def lock_locker():
    lckr = g.locker
    # lckr.lock()
    return f"Locker {lckr.get_index()} is locked."

def unlock_locker():
    lckr = g.locker
    #lckr.unlock()
    return f"Locker {lckr.get_index()} is unlocked."