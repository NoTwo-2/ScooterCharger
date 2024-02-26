# Serve registration and login pages here

from flask import Blueprint, g, request, redirect, url_for, session, send_file

from flaskr.sqlite_db import get_db

bp = Blueprint('pi', __name__, url_prefix='/socket.io')

@bp.route("/")
def connect():
    return send_file("socketio.html")