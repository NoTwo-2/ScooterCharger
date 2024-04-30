# Setup

1. Run `git clone (this repo)` in the desired directory.
2. `cd` into the `webserver` directory.
3. If using venv:
    1. Run `python -m venv .venv` if on macOS or Linux, `py -m venv .venv` if on Windows. This will create the virtual environment folders for the webserver. These should be ignored via `.gitignore`.
    2. Run `. .venv/bin/activate` if on macOS or Linux, `.venv\Scripts\activate` if on Windows. This will change the context of the current shell to the new virtual environment you have created.
    3. If using VSCode: 
        1. Press `CTRL+SHIFT+P` to open the command palette.
        2. Click `Python: Select Interpreter`
        3. Find the python binary or executable in `.venv/Scripts` and select it. This will ensure pylance is able to interpret and highlight code from venv libraries that you install.
4. Run `python -m pip install -r requirements.txt`. This will install all required dependencies.
5. Run `flask --app flaskr init-db`. This will initialize the database schema and create a new SQLite database instance locally.
6. Run `python run.py` to start the webserver.

# About

This directory contains everything needed to run the webserver for the scooter charging stations. The webserver has three main purposes:
1. To serve webpages to users that allow them to reserve and unlock lockers.
2. To serve webpages to admin users that allow them to manage charging stations and active reservations.
3. To facilitate Socketio connections between charging stations and the webserver to communicate status, unlock commands, etc.

# Additional Documentation

## Outgoing Email Address

Currently, all emails are sent from a temporary gmail account,which can be easily changed to another Gmail account.
1. Using the new account, enable 2-Step Verification.
2. Go here (`https://myaccount.google.com/apppasswords`) to generate an app password that will only be used by the ScooterCharger webserver. Copy the password to input later.
3. Navigate to the `/flaskr` folder in this directory and open `extensions.py`.
4. Update `OUT_EMAIL` with the new email address and `OUT_EMAIL_PASS` with the app password you copied. Save your changes.

To test:
1. In a browser window, log into ScooterCharger, then replace the URL path with `/notifs/home`. 
2. Click `Send email`. The page should read `Sent Email.` and the new account should have received an email from itself with the subject line `Test`.

## Socketio Documentation

All Socketio functionality is located in `events.py`.

### Server Side Event Listeners

#### "connect"
Client emits this automatically upon connection with the webserver. This will create a new instance of the `ChargingStation` class and assign the `client_sid` variable to the session id of the connection. The new `ChargingStation` instance will then be appended to the `connected_clients` array.

#### "disconnect"
Client emits this automatically upon connection termination, no matter the cause. This will remove the `ChargingStation` instance from the `connected_clients` array.

#### "init"
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

#### "json"
This will be how the client sends status updates and error messages to the server and should contain the following JSON:
```json
{
    "status_code" : 1, // This is required
    "error_msg" : "Failed to unlock locker 2", // This is conditionally optional (see below)
    "locker_list" : [ // This is required
        {
            "state" : "good",
            "temperature" : 90,
            "current" : 0,
            // More entries can be added here
        },
        {
            "state" : "disabled",
            "temperature" : 90,
            "current" : 50,
            // More entries can be added here
        },
        // More entries can be added here
    ]
}
```
This event will eventually handle logging and admin notifications, as well as keep track of expired reservations.

- **status_code** (Required) - This is a numeric representation of the status of the locker. 
    - `0` means there are no problems
    - `1` means an error has occured, but the charging station is still operational
    - `2` means a fatal error has occured and the charging station is no longer operational
- **error_msg** - This is a string containing a custom error message describing the error in more detail upon receiving a value greater than `0` in the `status_code`.
- **locker_list** - This is an array of JSON objects containing various information from each locker. Required values are provided below. **IMPORTANT**: every time the client emits this event, it must send information for *all lockers and in the same order*. This list is how lockers are given their indexes. Otherwise, the information provided here will only be used for logging purposes.
    - **state** - This stores the specific locker's state.
        - `"good"` means the locker is operating normally and available for reservation.
        - Anything other than `"good"` describes an error state, and means the locker is unable to be reserved by users.

### Client Side Event Listeners

#### "init"
The server sends this after the client emits the `"init"` event and will contain the following JSON:
```json
{
    "id" : 1,
    "status_rate" : 300
}
```

- **id** - The numerical id that this charging station should use to identify itself. Upon future connections, this should be provided when the client emits the `"init"` event (see [Server Side Event Listeners](#server-side-event-listeners)).
- **status_rate** - This is an integer representing how many seconds the client should wait in between sending status updates via the `"json"` event. The server will be expecting status updates at this rate, and will assume something is wrong if it doesn't receive them.

#### "unlock"
The server sends this when it wants a locker to be unlocked and will contain the following JSON:
```json
{
    "index" : 0
}
```
When the client receives this event, it should attempt to unlock the locker, and if successful, it should emit the `"json"` event (see [Server Side Event Listeners](#server-side-event-listeners)).

- **index** - The index of the locker the server wants the client to unlock. The first locker should always have an index of `0`.
