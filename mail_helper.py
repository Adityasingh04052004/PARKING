from flask_mail import Mail, Message
from celery_app import flask_app

mail = Mail(flask_app)

def send_email(to, subject, body, html=False):
    msg = Message(subject, recipients=[to])

    if html:
        msg.html = body
    else:
        msg.body = body

    mail.send(msg)
