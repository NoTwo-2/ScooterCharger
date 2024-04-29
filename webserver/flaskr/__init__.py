# This is where the application is initialized
# Import all blueprints here and add them in the create app function

import os
from flask import Flask, redirect, render_template, url_for
from .extensions import mail, OUT_EMAIL, OUT_EMAIL_PASS

def create_app() -> Flask:
    # Create instance of Flask object and set some config
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev', # TODO: Change this in prod
        DEBUG=True, # TODO: Change in prod
        DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
        # mail stuff
        MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com'),
        MAIL_PORT = os.getenv('MAIL_SERVER_PORT', 465),
        MAIL_USERNAME = os.getenv('MAIL_USERNAME', OUT_EMAIL),
        MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', False),
        MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', True),
        MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', OUT_EMAIL_PASS)
    )
    
    # Create instance folder for application
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Attatch socketio
    from .events import socketio
    socketio.init_app(app)
    
    # Attatch database methods to app
    from . import sqlite_db
    sqlite_db.init_app(app)
    
    # Import blueprints
    from . import auth
    app.register_blueprint(auth.bp)
    from . import user_view
    app.register_blueprint(user_view.bp)
    from . import admin
    app.register_blueprint(admin.bp)
    from . import notifs
    app.register_blueprint(notifs.bp)

    # mail stuff
    mail.init_app(app)

    @app.route("/")
    def route_to_home():
        return redirect("/home")
    
    return app