from celery_app import celery
import tasks   # registers all tasks

app = celery
