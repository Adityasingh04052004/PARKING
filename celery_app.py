import os
from celery import Celery
from celery.schedules import crontab
from app_factory import create_app

flask_app = create_app()

# ✅ Use REDIS_URL from environment (Render/Railway)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def make_celery(app):
    celery = Celery(
        app.import_name,
        broker=REDIS_URL,
        backend=REDIS_URL,
        include=["tasks"]
    )

    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return super().__call__(*args, **kwargs)

    celery.Task = ContextTask
    return celery


celery = make_celery(flask_app)

# ✅ Runs daily at 6 PM IST
celery.conf.beat_schedule = {
    "daily-reminder-job": {
        "task": "tasks.send_daily_reminders",
        "schedule": crontab(hour=18, minute=0),
    }
}

celery.conf.timezone = "Asia/Kolkata"
