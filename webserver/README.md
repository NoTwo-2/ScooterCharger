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

# API Documentation

Please update with API documentation as routes are added!