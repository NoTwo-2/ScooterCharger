from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="*")

@socketio.on("connect")
def handle_connect():
    print(f"SocketIO Connection Established")