# This is where the application is initialized
# Import all blueprints here and add them in the create app function

import os
from flask import Flask, redirect, render_template, url_for

def create_app() -> Flask:
    # Create instance of Flask object and set some config
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev', # TODO: Change this in prod
        DEBUG=True, # TODO: Change in prod
        DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
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
    # from . import api
    # app.register_blueprint(api.bp)

    @app.route("/")
    def route_to_auth():
        return redirect(url_for("auth.login"))
    
    return app