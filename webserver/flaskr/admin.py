# Serve admin pages here

from flask import Blueprint, g, request, redirect, url_for, session, render_template, flash

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
            return redirect("/view-charging-stations")
        case _:
            flash("???")
            return redirect('/home') # "Invalid action"

@bp.route('/edit-station/<cs_id>', methods=['POST'])
def edit_charging_station(cs_id):
    '''
    Updates info about charging station
    '''
    match request.form["action"]:
        case 'POST':
            if cs_id is None:
                flash("Incomplete URL.")
                return redirect(url_for("user_view.view_charging_stations"))
            
            cs_name = request.form['cs_name']
            cs_address = request.form['cs_address']
            gmaps_lon_lat = request.form['gmaps_lon_lat']
            if gmaps_lon_lat.strip() == "":
                cs_gmaps_link = request.form['cs_gmaps_link']
            else:
                cs_gmaps_link = "https://maps.google.com/maps?q=" + gmaps_lon_lat.replace(" ", "+", 1)
            
            db = get_db()
            db.execute(
                f"UPDATE CHARGING_STATION "
                f"SET CS_NAME = '{cs_name}', "
                f"CS_GMAPS_LINK = '{cs_gmaps_link}', "
                f"CS_ADDRESS = '{cs_address}' "
                f"WHERE CS_ID = {cs_id}"
            )
            db.commit()
            flash("Successfully changed charging station information!")
            return redirect(url_for('user_view.view_charging_stations'))
        case 'DELETE':
            if cs_id is None:
                return "Bad Request", 400
            
            db = get_db()
            db.execute(
                f"DELETE FROM CHARGING_STATION "
                f"WHERE CS_ID = {cs_id}"
            )
            db.commit()
            flash("Successfully deleted charging station.")
            return redirect(url_for('user_view.view_charging_stations'))
        case _:
            return "Bad Request", 400

# TODO: route to force unlock a locker?

@bp.before_request
def filter_admin():
    '''
    Redirects if session user is not an admin
    '''
    if not g.user:
        flash("Please login!")
        return redirect("/auth/login")
    access = g.user["ACCESS_TYPE"]
    if access != "ADMIN":
        flash("You aren't authorized to perform this action.")
        return redirect("/home")