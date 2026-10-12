import os

from flask import Flask

from config import Config
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_class=Config):
    """Build and return a configured Flask app."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Make sure the uploads folder exists before anyone uploads.
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "avatars"), exist_ok=True)

    # Connect the shared extension objects to this app.
    db.init_app(app)
    # render_as_batch lets later migrations change columns on SQLite.
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Import models so SQLAlchemy and Flask-Migrate know about the tables.
    from app import models  # noqa: F401

    # Blueprints: each feature registers its own group of routes.
    from app.main.routes import bp as main_bp
    from app.auth.routes import bp as auth_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    return app
