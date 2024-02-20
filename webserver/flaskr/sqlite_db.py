# https://flask.palletsprojects.com/en/3.0.x/tutorial/database/

import sqlite3

import click
from flask import current_app, g, Flask

def get_db():
    '''
    Stores a new db connection in g if one is not present
    '''
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        # Returned rows will behave like dicts
        g.db.row_factory = sqlite3.Row
        
    return g.db

def close_db(e=None):
    '''
    Closes a db connection in g
    '''
    db = g.pop('db', None)
    
    if db is not None:
        db.close()

def init_db():
    '''
    Runs the SQL code in schema.sql
    Used on first time startup 
    '''
    db = get_db()
    
    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))

@click.command('init-db')
def init_db_command():
    '''
    Clears existing data and creates new tables. 
    (https://flask.palletsprojects.com/en/3.0.x/tutorial/database/)
    '''
    init_db()
    click.echo('Initialized database')
    
def init_app(app: Flask):
    '''
    Attatches relevant functions to the flask application
    '''
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)