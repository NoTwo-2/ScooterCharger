from flask import Flask, Blueprint

bp = Blueprint('api', __name__, url_prefix='/api')

# Place any API routes here
# None of these should return rendered templates