# Serve registration and login pages here

from flask import Blueprint, g, request, redirect, url_for, session, render_template, flash

from werkzeug.security import check_password_hash, generate_password_hash

from flaskr.sqlite_db import get_db

from enum import Enum

from .notifs import notify

import secrets

from smtplib import SMTPAuthenticationError

bp = Blueprint('auth', __name__, url_prefix='/auth')

# Key to hold user_id
USER_ID_COOKIE = "user_id"
# Enum to determine AccessType
class AccessType(Enum):
    STUDENT = 0
    ADMIN = 1
    BOX = 2

#generate a token for email
def generate_verification_token():
    return secrets.token_urlsafe(16)

#send verification email
def send_verification_email(email, token):
    subject = 'Verify Your Email'
    body = f'Click the link to verify your email: {url_for("auth.verify_email", token=token, _external=True)}'
    notify([email], subject, body)

@bp.route('/register', methods=('GET', 'POST'))
def register():
    '''
    Handles registration logic and login page display
    '''
    match request.method:
        case 'POST':
            db = get_db()
            
            access_type = 'STUDENT'
            email = request.form['email']
            password = request.form['password']
            
            if not access_type or not email or not password:
                flash("One or more required fields was not filled. Please try again.", "warning")
                return redirect(url_for("auth.register"))
            if not (access_type in [at.name for at in AccessType]):
                access_type = AccessType(0).name
            verification_token = generate_verification_token()
            passkey = generate_password_hash(password)
            
            try:
                print("sending email")
                send_verification_email(email, verification_token)
            except (ValueError, SMTPAuthenticationError):
                print("except caught")
                flash(f"Unable to send verification email to {email}, check the validity of your email and try again", "error")
                return redirect(url_for("auth.register"))
            else:
                print("except not caught")
                try:
                    db.execute(
                        f"INSERT INTO APPUSER (ACCESS_TYPE, EMAIL, PASSKEY, VERIFICATION_TOKEN) VALUES ('{access_type}', '{email}', '{passkey}', '{verification_token}')"
                    )
                    db.commit()
                except db.IntegrityError:
                    flash("An account associated with this email already exists.", "warning")
                    return redirect(url_for("auth.register"))
                else:
                    flash("An email with a verification link has been sent to your email address. Please verify your email.", "info")
                    return redirect(url_for("auth.login"))
        case 'GET':
            return render_template("auth/register.html")
        case _:
            return "Bad Request", 400
        
    # TODO: The page will be rendered down here eventually
@bp.route('/verify/<token>')
def verify_email(token):
    db = get_db()
    user = db.execute(
        "SELECT * FROM APPUSER WHERE VERIFICATION_TOKEN = ?",
        (token,)
    ).fetchone()
    if user is None:
        flash("Invalid verification token.", "error")
        return redirect(url_for("auth.login"))
    db.execute(
        "UPDATE APPUSER SET IS_VERIFIED = 1 WHERE EMAIL = ?",
        (user['EMAIL'],)
    )
    db.commit()
    flash("Your email has been successfully verified. You can now log in.", "info")
    return redirect(url_for("auth.login"))
     
@bp.route('/login', methods=('GET', 'POST'))
def login():
    '''
    Handles login logic and login page display
    '''
    match request.method:
        case 'POST':
            db = get_db()
            
            email = request.form['email']
            password = request.form['password']
            
            user = db.execute(f"SELECT rowid, * FROM APPUSER WHERE EMAIL = '{email}'").fetchone()
            if user is None:
                flash("Could not find an account associated with this email.", "error")
                return redirect(url_for("auth.login"))
            if user['IS_VERIFIED'] != 1:
                flash("You have not verified your email", "warning")
                return redirect(url_for("auth.login"))
            password_correct = check_password_hash(user['PASSKEY'], password)
            if not password_correct:
                flash("Incorrect email or password.", "warning")
                return redirect(url_for("auth.login"))
            
            # JWT REPLACEMENT!
            session.clear()
            session[USER_ID_COOKIE] = user['rowid']
            # if user is admin
            if user['ACCESS_TYPE'] == "ADMIN":
                flash("Login successful! Welcome, admin user!", "info")
                return redirect(url_for("admin.home"))
            flash("Login successful!", "info")
            return redirect(url_for("user_view.home"))
        case 'GET':
            return render_template("auth/login.html")
        case _:
            return "Bad Request", 400


@bp.before_app_request
def load_user():
    '''
    This adds all user info from the DB into g to be used by any app request
    '''
    db = get_db()
    
    user_id = session.get(USER_ID_COOKIE)
    
    if user_id is None:
        g.user = None
    else:
        g.user = db.execute(f"SELECT rowid, * FROM APPUSER WHERE rowid = '{user_id}'").fetchone()