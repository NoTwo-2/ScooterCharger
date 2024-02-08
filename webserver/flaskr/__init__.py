import os
from flask import Flask

def create_app() -> Flask:
    # Create instance of Flask object and set some config
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev' # TODO: Change this in prod
    )
    
    # Check for existance of instance folder using OS
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    return app