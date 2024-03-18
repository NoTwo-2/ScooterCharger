from flaskr import create_app, events

app = create_app()

events.socketio.run(app, host="0.0.0.0", port=5000)