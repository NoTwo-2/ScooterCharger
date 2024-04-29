from flask import Blueprint, g, request, redirect, url_for, session, render_template, current_app
from flask_mail import Message
from .extensions import mail, OUT_EMAIL, OUT_EMAIL_PASS
import os

bp = Blueprint('notifs', __name__, url_prefix='/notifs') 

# testing, don't really need a page to send manually
@bp.route('/home', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        sendTo = [OUT_EMAIL]
        subject = "Test"
        body = "Testing"
        if notify(sendTo, subject, body) == "sent":
            return "Sent Email."
    return render_template('auth/email_demo.html')

def notify(sendTo, subject, message):
    msg = Message(subject, sender=OUT_EMAIL, recipients=sendTo)
    msg.body = message
    try:
        mail.send(msg)
    except Exception as e:
        print(e)
        return e.__str__()
    return "sent"