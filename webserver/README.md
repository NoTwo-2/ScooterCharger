# Setup

Learn how to initialize this directory with an environment (venv) [here](https://flask.palletsprojects.com/en/3.0.x/installation/).
#### Activate venv in shell
- Linux: `. .venv/bin/activate`
- Windows: `.venv\Scripts\activate`

We are currently using: 
- Flask: `pip install flask`
- Flask-SocketIO: `pip install flask-socketio`


### If using VS Code and venv:
`CTRL+SHIFT+P`, `Python: Select Interpreter`, select the python bin/exe in your `.venv` file.

### To test the app
If using venv, make sure your shell prompt displays `.venv` (see the above link). The path to the bin/exe for flask wont exist in environment variables otherwise.

If you are running this for the first time (or you want to reset the sqlite database), be sure to run `flask --app flaskr init-db` before running the app.
In this directory, run the `run.py` python script.

# Socketio Documentation

## Server Side Event Listeners

### "connect"
Client emits this automatically upon connection with the webserver. This will create a new instance of the `ChargingStation` class and assign the `client_sid` variable to the session id of the connection. The new `ChargingStation` instance will then be appended to the `connected_clients` array.

### "disconnect"
Client emits this automatically upon connection termination, no matter the cause. This will remove the `ChargingStation` instance from the `connected_clients` array.

### "init"
The client should send this immediatley after successful connection to the webserver and should contain the following JSON:
```json
{
    "auth" : "dev", // This is required.
    "id" : 1, // This is conditionally optional (see below)
}
```
This will verify the authenticity of the client attempting a connection and initialize the `ChargingStation` instance with an id. This will then emit the `"init"` event to the connected client (see [Client Side Event Listeners](#client-side-event-listeners)). 

- **auth** (Required) -  This is a string the client must provide to the server when it emits the `"init"` event. The server will expect `"dev"` for development purposes.
- **id** - This is the ID of the connected charging station and will correspond to the id of its entry in the database. This field should only be ommitted if this clent has not yet made a connection to the webserver. If this is not supplied, a new entry will be created in the database.

### "json"
This will be how the client sends status updates and error messages to the server and should contain the following JSON:
```json
{
    "status_code" : 1, // This is required
    "error_msg" : "Failed to lock locker 2", // This is conditionally optional (see below)
    "locker_list" : [ // This is required
        {
            "state" : "locked",
            "temperature" : 90,
            "current" : 0,
            // More entries can be added here
        },
        {
            "state" : "unlocked",
            "temperature" : 90,
            "current" : 50,
            // More entries can be added here
        },
        // More entries can be added here
    ]
}
```
This event will eventually handle logging and admin notifications, as well as keep track of expired reservations.

- **status_code** (Required) - This is a numeric representation of the status of the locker. `0` means there are no problems, `1` means an error has occured, but the charging station is still operational, `2` means a fatal error has occured and the charging station is no longer operational.
- **error_msg** - This is a string containing a custom error message describing the error in more detail upon receiving a `1` or `2` in the `status_code`.
- **locker_list** - This is an array of JSON objects containing various information from each locker. Required values are provided below. **IMPORTANT**: every time the client emits this event, it must send information for *all lockers and in the same order*. This list is how lockers are given their indexes. Otherwise, the information provided here will only be used for logging purposes.
    - **state** - This stores whether the specific locker is available or not.

## Client Side Event Listeners

### "init"
The server sends this after the client emits the `"init"` event and will contain the following JSON:
```json
{
    "id" : 1,
    "status_rate" : 300
}
```

- **id** - The numerical id that this charging station should use to identify itself. Upon future connections, this should be provided when the client emits the `"init"` event (see [Server Side Event Listeners](#server-side-event-listeners)).
- **status_rate** - This is an integer representing how many seconds the client should wait in between sending status updates via the `"json"` event. The server will be expecting status updates at this rate, and will assume something is wrong if it doesn't receive them.

### "lock"
The server sends this when it wants a locker to be locked and will contain the following JSON:
```json
{
    "index" : 0
}
```
When the client receives this event, it should attempt to lock the locker, and if successful, it should emit the `"locked"` event (see [Server Side Event Listeners](#server-side-event-listeners)).

- **index** - The index of the locker the server wants the client to lock. The first locker should always have an index of `0`.

### "unlock"
Similar to the `"lock"` event, the server sends this when it wants a locker to be unlocked and will contain the following JSON:
```json
{
    "index" : 0
}
```
When the client receives this event, it should attempt to unlock the locker, and if successful, it should emit the `"unlocked"` event (see [Server Side Event Listeners](#server-side-event-listeners)).

- **index** - The index of the locker the server wants the client to unlock. The first locker should always have an index of `0`.
