# Serve admin pages here

from flask import Blueprint, g, request, redirect, url_for, session, render_template, flash

from flaskr.sqlite_db import get_db
from .events import connected_clients, Locker, ChargingStation
from .notifs import notify
import secrets
from re import search

bp = Blueprint('admin', __name__, url_prefix='/admin')
# Generate a token for email
def generate_verification_token():
    return secrets.token_urlsafe(16)

# Send verification email
def send_verification_email(email, token):
    subject = 'Verify Your Email'
    body = f'Click the link to verify your email: {url_for("auth.verify_email", token=token, _external=True)}'
    notify([email], subject, body)

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
                flash("Incomplete URL.","error")
                return redirect(url_for("user_view.view_charging_stations"))
            
            cs_name = request.form['cs_name']
            cs_address = request.form['cs_address']
            gmaps_lon_lat = request.form['gmaps_lon_lat']
            if gmaps_lon_lat.strip() == "":
                cs_gmaps_link = request.form['cs_gmaps_link']
            else:
                lat_lon_patt = "^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?),\s*[-+]?(180(\.0+)?|((1[0-7]\d)|([1-9]?\d))(\.\d+)?)$" # Thanks stack overflow  
                if search(lat_lon_patt, gmaps_lon_lat) is None:
                    cs_gmaps_link = None
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
            flash("Successfully changed charging station information!","info")
            return redirect(url_for('user_view.view_charging_stations'))
        case 'DELETE':
            if cs_id is None:
                return "Bad Request", 400
            
            db = get_db()
            db.execute(
                f"UPDATE APPUSER "
                f"SET RESERVED_CS_ID = NULL, "
                f"RESERVED_CS_SPACE_I = NULL "
                f"WHERE RESERVED_CS_ID = {cs_id}"
            )
            db.execute(
                f"DELETE FROM CHARGING_STATION "
                f"WHERE CS_ID = {cs_id}"
            )
            db.commit()
            flash("Successfully deleted charging station.","info")
            return redirect(url_for('user_view.view_charging_stations'))
        case _:
            return "Bad Request", 400

@bp.route('/unlock-locker/<cs_id>/<l_id>', methods=['POST'])
def unlock_locker(cs_id, l_id):
    '''
    Forcibly unlocks a locker
    '''
    if cs_id is None or l_id is None:
        flash("Incomplete URL.","error")
        return redirect(url_for("user_view.view_charging_stations"))
    
    cs_id = int(cs_id)
    l_id = int(l_id)
    
    locker = None
    for cs in connected_clients:
        if cs.id == cs_id:
            if l_id < len(cs.locker_list):
                locker = cs.locker_list[l_id]
                break
    if locker is None:
        flash("The charging station associated with this locker is no longer connected to the server.","warning")
        return redirect(url_for("user_view.view_charging_stations"))
    
    locker.unlock()
    flash("Sent unlock command to locker.","info")
    return redirect(url_for("user_view.view_charging_stations"))

@bp.route('/terminate-reservation/<cs_id>/<l_id>', methods=['POST'])
def terminate_reservation(cs_id, l_id):
    '''
    Forcibly terminates an active reservation.
    '''
    if cs_id is None or l_id is None:
        flash("Incomplete URL.","error")
        return redirect(url_for("user_view.view_charging_stations"))
    
    cs_id = int(cs_id)
    l_id = int(l_id)
    
    locker = None
    for cs in connected_clients:
        if cs.id == cs_id:
            if l_id < len(cs.locker_list):
                locker = cs.locker_list[l_id]
                break
    if locker is None:
        flash("The charging station associated with this locker is no longer connected to the server.","warning")
        return redirect(url_for("user_view.view_charging_stations"))
    
    locker.unreserve(reason="Admin Requested Termination")
    flash("Successfully unreserved locker.","info")
    return redirect(url_for("user_view.view_charging_stations"))

@bp.route('/change-email', methods=['GET', 'POST'])
def change_email():
    match request.method:
        case 'POST':
            db = get_db()
            new_email = request.form['new_email']
            # Validate the new email address
            verification_token = generate_verification_token()
            try:
                db.execute(
                    f"UPDATE APPUSER SET EMAIL = '{new_email}', VERIFICATION_TOKEN = '{verification_token}' WHERE ACCESS_TYPE = 'ADMIN'"
                )
                db.commit()
            except db.IntegrityError:
                flash("An account associated with this email already exists.", "warning")
                return redirect(url_for("admin.change_email"))
            else:
                try:
                    send_verification_email(new_email, verification_token)
                except ValueError:
                    flash(f"Unable to send verification email to {new_email}, check the validity of your email and try again", "error")
                    return redirect(url_for("admin.change_email"))
                except:
                    flash(f"check the validity of your email and try again", "error")
                    return redirect(url_for("admin.change_email"))
                else:
                    flash('Email updated successfully! A verification link has been sent to your new email.', 'info')
                    return redirect(url_for("auth.login"))
        case 'GET':
            return render_template("auth/change_email.html")
        case _:
            return "Bad Request", 400
 
@bp.before_request
def filter_admin():
    '''
    Redirects if session user is not an admin
    '''
    if not g.user:
        flash("Please login!","warning")
        return redirect("/auth/login")
    access = g.user["ACCESS_TYPE"]
    if access != "ADMIN":
        flash("You aren't authorized to perform this action.","error")
        return redirect("/home")