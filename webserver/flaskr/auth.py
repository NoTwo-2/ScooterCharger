# Serve registration and login pages here

from flask import Blueprint, g, request, redirect, url_for, session, render_template

from werkzeug.security import check_password_hash, generate_password_hash

from flaskr.sqlite_db import get_db

from enum import Enum

bp = Blueprint('auth', __name__, url_prefix='/auth')

# Key to hold user_id
USER_ID_COOKIE = "user_id"
# Enum to determine AccessType
class AccessType(Enum):
    STUDENT = 0
    ADMIN = 1
    BOX = 2

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
                return "Bad Request", 400
            if not (access_type in [at.name for at in AccessType]):
                access_type = AccessType(0).name
            # TODO: Insert some sort of regex for email verification
            passkey = generate_password_hash(password)
            print(passkey)
            
            try:
                db.execute(
                    f"INSERT INTO APPUSER (ACCESS_TYPE, EMAIL, PASSKEY) VALUES ('{access_type}', '{email}', '{passkey}')"
                )
                db.commit()
            except db.IntegrityError:
                return "Conflict", 409 # TODO: Maybe render registration page with a custom message here
            else:
                return redirect(url_for("auth.login"))
        case 'GET':
            return render_template("auth/register.html")
        case _:
            return "Bad Request", 400
        
    # TODO: The page will be rendered down here eventually
        
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
            password_correct = check_password_hash(user['PASSKEY'], password)
            if (user is None) or (not password_correct):
                return "Bad Request", 400 # TODO: Maybe render login page with a custom message here
            
            # JWT REPLACEMENT!
            session.clear()
            session[USER_ID_COOKIE] = user['rowid']
            return "OK", 200 # TODO: User landing page(s)?
        case 'GET':
            return render_template("auth/login.html")
        case _:
            return "Bad Request", 400
    
    # TODO: The page will be rendered down here eventually

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