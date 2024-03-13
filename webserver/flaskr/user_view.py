from flask import Flask, Blueprint, request, g, session, redirect, url_for

from .events import connected_clients
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
    
    # check for active reseervation
    user_id = g.user["ID"]
    if not g.user["RESERVED_CS_SPACE_I INT"]:
        return redirect('/view-available')

    active_res = g.user["RESERVED_CS_SPACE_I INT"]
    return redirect(url_for('/manage-locker'))


# Lockers Page (2)
# show charging stations with available lockers and location
@bp.route('/view-available')
def show_available_lockers():

    # list of dictionaries (cs table + num_lockers)
    avail_lckr = []

    # list of tuples (cs.id, num_lockers)
    avail = []

    # add cs with available lockers to avail list with num_lockers
    for cs in connected_clients:
        has_unreserved = 1
        num_lockers = 0

        if cs.locker_list:
            for lckr in cs.locker_list:
                if lckr.is_reserved:
                    has_unreserved = 0
                    break
                else:
                    num_lockers += 1
            if has_unreserved:
                avail.append((cs.id, num_lockers))

    # get cs table data
    db = get_db()
    records = db.execute(f"SELECT * FROM CHARGING_STATION").fetchall()

    # put location and num_locker into dictionary
    for row in records:
        if cs[0] == row[0]:
            avail_lckr.append({
                "cs_id": row[0],
                "cs_name": row[1],
                "cs_gmap_link": row[2],
                "cs_address": row[3],
                "cs_num_avail": cs[1]
            })
            break

    return avail_lckr


# Reservation Form Page (3)
# select a charging station and reserve locker
@bp.route('/reserve-locker/<cs_id>', methods=['GET', 'POST'])
def reserve_locker(cs_id):

    # check for account
    if not g.user:
        return redirect('/auth/login')
    user_id = g.user["ID"]

    # find selected charging station object
    charger = None
    for client in connected_clients:
        if cs_id == client.id:
            charger = client
            break

    if not charger or not charger.locker_list:
        return "Charging Station not found.", redirect('/view-available')

    # find available locker
    lckr = None
    full = True
    for box in charger.locker_list:
        if not box.is_reserved:
            full = False
            lckr = box
    if full:
        return "Charging Station full.", redirect('/view-available')
    
    # start reservation
    reserve_time = request.form['reserve_time']
    lckr.reserve(reserve_time)
    g.locker = lckr

    db = get_db()
    db.execute(
        f"UPDATE APPUSER "
        f"SET RESERVED_CS_ID = {cs_id}, "
            f"RESERVED_CS_SPACE_I = {lckr.get_index()} "
        f"WHERE ID = {user_id}"
    )

    return redirect('/manage-locker')


# Reservation Management Page (4)
# cancel reservation, lock/unlock locker
@bp.route('/manage-locker', methods=['GET', 'POST'])
def cancel_reservation():

    # check for account
    if not g.user:
        return redirect('/auth/login')
    user_id = g.user["ID"]
    
    # check for reservation
    if not g.locker:
        return "No active reservation.", redirect('/view-available')
    lckr = g.locker
    
    # end reservation
    lckr.unreserve()
    g.locker = None

    db = get_db()
    db.execute(
        f"UPDATE APPUSER "
        f"SET RESERVED_CS_ID = NULL, "
            f"RESERVED_CS_SPACE_I = NULL "
       f"WHERE ID = {user_id}"
    )

    return redirect('/home')

def lock_locker():
    lckr = g.locker
    # lckr.lock()
    return f"Locker {lckr.get_index()} is locked."

def unlock_locker():
    lckr = g.locker
    #lckr.unlock()
    return f"Locker {lckr.get_index()} is unlocked."