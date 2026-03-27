from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from config import Config


db = SQLAlchemy()
mail = Mail()


def create_app():
    """Application factory that creates and configures the Flask app."""
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    mail.init_app(app)

    # Import and register blueprints
    from .routes import main_bp

    app.register_blueprint(main_bp)

    # Create database tables
    with app.app_context():
        from . import models  # noqa: F401

        db.create_all()

    return app
