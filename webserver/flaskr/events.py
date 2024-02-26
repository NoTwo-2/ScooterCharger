from flask_socketio import SocketIO

socketio = SocketIO()

@socketio.on("connect")
def handle_connect():
    print(f"SocketIO Connection Established")