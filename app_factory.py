from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache
import os

db = SQLAlchemy()
cache = Cache()


def create_app():
    app = Flask(__name__, template_folder="templates")

    # ✅ BASIC CONFIG (use env variables in deployment)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "CHANGE_THIS_SECRET_KEY")

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # ✅ Ensure instance folder exists (important for deployment)
    instance_dir = os.path.join(BASE_DIR, "instance")
    os.makedirs(instance_dir, exist_ok=True)

    db_path = os.path.join(instance_dir, "parking_v2.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{db_path}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # ✅ EMAIL CONFIG (NEVER hardcode in deployment)
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True") == "True"

    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")

    app.config["MAIL_DEFAULT_SENDER"] = os.getenv(
        "MAIL_DEFAULT_SENDER",
        app.config["MAIL_USERNAME"]
    )

    # ✅ CACHE CONFIG (use cloud redis URL in deployment)
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    app.config["CACHE_TYPE"] = "RedisCache"
    app.config["CACHE_REDIS_URL"] = redis_url
    app.config["CACHE_DEFAULT_TIMEOUT"] = 30

    # ✅ Init extensions
    db.init_app(app)
    cache.init_app(app)

    # ✅ Blueprints
    from backend.routes import bp
    app.register_blueprint(bp)

    return app
