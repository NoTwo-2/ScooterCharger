# Notes

## Jacob
- The database should store the reserved locker id in the user table for easy access
- The route should handle the updating of this information
- If the socketio connection is severed (and the command to unlock is sent to all locker spaces), the user table should not be updated, 
    and the incongruency should be handled properly in the route
- The database should store the last status code of a locker in the locker table