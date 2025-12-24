from app_factory import create_app
from celery_app import celery   # Only import celery, NOT init_celery

app = create_app()

if __name__ == "__main__":
    app.run(port=7000, debug=True)
