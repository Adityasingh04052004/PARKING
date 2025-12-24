from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache
import os

db = SQLAlchemy()
cache = Cache()

def create_app():
    app = Flask(__name__, template_folder="templates")

    # BASIC CONFIG
    app.config["SECRET_KEY"] = "CHANGE_THIS_SECRET_KEY"

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(BASE_DIR, "instance", "parking_v2.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # EMAIL CONFIG
    app.config["MAIL_SERVER"] = "smtp.gmail.com"
    app.config["MAIL_PORT"] = 587
    app.config["MAIL_USE_TLS"] = True
    
    app.config["MAIL_USERNAME"] = "adityasinghnew45@gmail.com"  
    app.config["MAIL_PASSWORD"] = "iysi mchi dtdl cvaf"     # 16-char App Password

    # Default email sender
    app.config["MAIL_DEFAULT_SENDER"] = app.config["MAIL_USERNAME"]

    # CACHE CONFIG
    app.config["CACHE_TYPE"] = "RedisCache"
    app.config["CACHE_REDIS_URL"] = "redis://localhost:6379/0"
    app.config["CACHE_DEFAULT_TIMEOUT"] = 30

    # Init extensions
    db.init_app(app)
    cache.init_app(app)

    # Blueprint
    from backend.routes import bp
    app.register_blueprint(bp)

    return app
