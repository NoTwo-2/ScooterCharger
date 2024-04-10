from flask import Blueprint, g, request, redirect, url_for, session, render_template, current_app
from flask_mail import Message
from .extensions import mail
import os

bp = Blueprint('notifs', __name__, url_prefix='/notifs') 

# testing, don't really need a page to send manually
@bp.route('/home', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        msg = Message("Test", sender='ScooterCharger@mst.edu', recipients=['imbeahe@gmail.com', 'e4228557@gmail.com'])
        msg.body = "Testing"
        mail.send(msg)
        return "Sent Email."
    return render_template('auth/email_demo.html')

def notify(sendTo, subject, message):
    msg = Message(subject, sender='ScooterCharger@mst.edu', recipients=sendTo)
    msg.body = message
    mail.send(msg)
    return None
