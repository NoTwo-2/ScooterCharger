# Serve admin pages here

from flask import Blueprint, g, request, redirect, url_for, session, render_template

from flaskr.sqlite_db import get_db
from .events import connected_clients, Locker, ChargingStation

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/home', methods=['GET'])
def home():
    '''
    Landing page for admin users
    '''
    match request.method:
        case 'GET':
            # TODO: Landing page for admins, should have link to
            # 1) locker list/manage locker
            # 2) station list
            # 3) ...
            return redirect("/admin/station-list")
        case _:
            return "Bad Request", 400

@bp.route('/station-list', methods=['GET'])
def list_charging_stations():
    '''
    Serves a page listing all charging stations and their properties
    '''
    match request.method:
        case 'GET':
            stations = []
            # get db data
            db = get_db()
            rows = db.execute(f"SELECT rowid, * FROM CHARGING_STATION").fetchall()
            
            # loop thru each db entry
            for row in rows:
                station = dict()
                
                # database entries
                for key in row.keys():
                    station[key] = row[key]
                
                cs: ChargingStation = None
                for client in connected_clients:
                    if client.id == row["rowid"]:
                        cs = client
                        break
                
                if cs:
                    station["status"] = "Online"
                    # last status update
                    station["last_status_time"] = str(cs.last_stat_time)
                    # number of available lockers
                    locker_avail = 0
                    for locker in cs.locker_list:
                        if not locker.is_reserved: locker_avail += 1
                    station["num_avail_lockers"] = locker_avail
                else:
                    station["status"] = "Offline"
                
                stations.append(station)
            # TODO: Template
            return stations
        case _:
            return "Bad Request", 400

@bp.route('/edit-station/<cs_id>', methods=['POST'])
def edit_charging_station(cs_id):
    '''
    Updates info about charging station
    '''
    match request.method:
        case 'POST':
            if cs_id is None:
                return "Bad Request", 400
            
            cs_name = request.form['cs_name']
            cs_address = request.form['cs_address']
            cs_gmaps_link = request.form['cs_gmaps_link']
            
            db = get_db()
            db.execute(
                f"UPDATE CHARGING_STATION "
                f"SET CS_NAME = '{cs_name}', "
                f"CS_GMAPS_LINK = '{cs_gmaps_link}', "
                f"CS_ADDRESS = '{cs_address}' "
                f"WHERE rowid = {cs_id}"
            )
            db.commit()            
        case _:
            return "Bad Request", 400

@bp.before_request
def filter_admin():
    '''
    Redirects if session user is not an admin
    '''
    if not g.user:
        return redirect("/auth/login")
    access = g.user["ACCESS_TYPE"]
    if access != "ADMIN":
        return redirect("/home")