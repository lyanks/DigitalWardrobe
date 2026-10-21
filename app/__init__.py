import os

from flask import Flask

from config import Config
from app.extensions import babel, csrf, db, login_manager, migrate, oauth


def create_app(config_class=Config):
    """Build and return a configured Flask app."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    if app.config["BEHIND_PROXY"]:
        # Read the X-Forwarded-Proto / X-Forwarded-Host headers the proxy
        # adds (one proxy, so trust one hop). See BEHIND_PROXY in config.py.
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Make sure the uploads folder exists before anyone uploads.
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Connect the shared extension objects to this app.
    db.init_app(app)
    # render_as_batch lets later migrations change columns on SQLite.
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    csrf.init_app(app)
    oauth.init_app(app)

    # Languages. get_locale picks English or Ukrainian for each request;
    # compile_translations refreshes the compiled translations if needed.
    from app.i18n import compile_translations, get_locale
    babel.init_app(app, locale_selector=get_locale)
    compile_translations(app)
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

    # Day and month names in the page's language, and | tr for words that
    # come from the database (category names, colours...).
    import flask_babel
    from app import i18n
    app.jinja_env.filters["tr"] = i18n.tr
    app.jinja_env.filters["weekday"] = i18n.weekday
    app.jinja_env.filters["weekday_short"] = i18n.weekday_short
    app.jinja_env.filters["month_name"] = i18n.month_name
    app.jinja_env.filters["month_year"] = i18n.month_year
    app.jinja_env.globals["js_texts"] = i18n.js_texts
    app.jinja_env.globals["LANGUAGES"] = i18n.LANGUAGES
    app.jinja_env.globals["current_language"] = lambda: str(flask_babel.get_locale())

    # Terminal commands: flask photos cut-out / restore, flask goals (app/commands.py).
    from app.commands import goals, invites, photos
    app.cli.add_command(photos)
    app.cli.add_command(goals)
    app.cli.add_command(invites)

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
    from app.trips.routes import bp as trips_bp
    from app.tutorial.routes import bp as tutorial_bp
    from app.admin.routes import bp as admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(wardrobe_bp)
    app.register_blueprint(outfits_bp)
    app.register_blueprint(planner_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(trips_bp)
    app.register_blueprint(tutorial_bp)
    app.register_blueprint(welcome_bp)
    app.register_blueprint(admin_bp)

    # {% if is_admin(current_user) %} shows the Admin link only to you.
    from app.admin.access import is_admin
    app.jinja_env.globals["is_admin"] = is_admin

    return app
