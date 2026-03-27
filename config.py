import os


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Basic configuration for the Flask app."""

    # Change this to a strong, random value in production
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

    # SQLite database in the instance/ folder
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "app.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Email configuration for password reset
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in [
        'true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['your-email@gmail.com']
