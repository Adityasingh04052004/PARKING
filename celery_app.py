from celery import Celery
from app_factory import create_app

from celery.schedules import crontab

flask_app = create_app()

def make_celery(app):
    celery = Celery(
        app.import_name,
        broker="redis://localhost:6379/0",
        backend="redis://localhost:6379/0",   # IMPORTANT!!
        include=["tasks"]                     # Load tasks
    )

    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return super().__call__(*args, **kwargs)

    celery.Task = ContextTask
    return celery

celery = make_celery(flask_app)

celery.conf.beat_schedule = {
    "daily-reminder-job": {
        "task": "tasks.send_daily_reminders",
        "schedule": crontab(minute="*/1"),
 # Runs daily at 6 PM
    }
}

celery.conf.timezone = "Asia/Kolkata"

