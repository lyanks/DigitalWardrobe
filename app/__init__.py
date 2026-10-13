import os

from flask import Flask

from config import Config
from app.extensions import csrf, db, login_manager, migrate, oauth


def create_app(config_class=Config):
    """Build and return a configured Flask app."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Make sure the uploads folder exists before anyone uploads.
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Connect the shared extension objects to this app.
    db.init_app(app)
    # render_as_batch lets later migrations change columns on SQLite.
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    csrf.init_app(app)
    oauth.init_app(app)
    if app.config["GOOGLE_CLIENT_ID"]:
        oauth.register(
            "google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            # Google publishes all its login URLs at this address.
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    # {{ some_date | date }} in any template prints it as 14.10.2026.
    from app.dates import format_date
    from app.filters import format_price, shop_name, swatch
    from app.themes import text_on
    app.jinja_env.filters["date"] = format_date
    app.jinja_env.filters["price"] = format_price
    app.jinja_env.filters["shop_name"] = shop_name
    app.jinja_env.filters["swatch"] = swatch
    app.jinja_env.filters["text_on"] = text_on

    # Terminal commands: flask photos cut-out / restore (app/commands.py).
    from app.commands import photos
    app.cli.add_command(photos)

    # Import models so SQLAlchemy and Flask-Migrate know about the tables.
    from app import models  # noqa: F401

    # Blueprints: each feature registers its own group of routes.
    from app.main.routes import bp as main_bp
    from app.auth.routes import bp as auth_bp
    from app.wardrobe.routes import bp as wardrobe_bp
    from app.outfits.routes import bp as outfits_bp
    from app.planner.routes import bp as planner_bp
    from app.api.routes import bp as api_bp
    from app.welcome.routes import bp as welcome_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(wardrobe_bp)
    app.register_blueprint(outfits_bp)
    app.register_blueprint(planner_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(welcome_bp)

    return app
