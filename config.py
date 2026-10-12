import os

# The folder this file lives in = the project root.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Flask uses SECRET_KEY to sign cookies (sessions, login, CSRF).
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    # Where the database lives. SQLite = one file in the project root.
    # Later, set DATABASE_URL to a PostgreSQL URL and nothing else changes.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "wardrobe.db")
    )

    # User photos go to uploads/ (ignored by Git).
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    # Reject any request bigger than 4 MB (Flask answers 413 by itself).
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}


class TestConfig(Config):
    TESTING = True
    # ":memory:" = a brand-new empty database in RAM for every test.
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # Tests post forms directly, without first loading the page that holds
    # the CSRF token, so switch the check off here (and only here).
    WTF_CSRF_ENABLED = False
