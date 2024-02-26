from flaskr import create_app, events

app = create_app()

events.socketio.run(app)