# Serve registration and login pages here

from flask import Blueprint, g, request, redirect, url_for, session

from werkzeug.security import check_password_hash, generate_password_hash

from flaskr.sqlite_db import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')

USER_ID_COOKIE = "user_id"

@bp.route('/register', methods=('GET', 'POST'))
def register():
    '''
    Handles registration logic and login page display
    '''
    match request.method:
        case 'POST':
            db = get_db()
            
            username = request.form['username']
            password = request.form['password']
            if not username or not password:
                return "Bad Request", 400
            
            try:
                db.execute(
                    f'INSERT INTO user (username, password) VALUES ({username}, {generate_password_hash(password)})'
                )
                db.commit()
            except db.IntegrityError:
                return "Conflict", 409 # TODO: Maybe render registration page with a custom message here
            else:
                return redirect(url_for("auth.login"))
        case 'GET':
            pass
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
            
            username = request.form['username']
            password = request.form['password']
            
            user = db.execute(f'SELECT * FROM user WHERE username = {username}')
            if (user is None) or (not check_password_hash(user['password'], password)):
                return "Bad Request", 400 # TODO: Maybe render login page with a custom message here
            
            # JWT REPLACEMENT!
            session.clear()
            session[USER_ID_COOKIE] = user['id']
            return "OK", 200 # TODO: User landing page(s)?
            
        case 'GET':
            pass
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
        g.user = db.execute(f'SELECT * FROM user WHERE id = {user_id}').fetchone()