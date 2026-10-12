from flask import Flask, render_template

from config import Config


def create_app(config_class=Config):
    """Build and return a configured Flask app."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    @app.route("/")
    def index():
        return render_template("index.html", title="Home")

    return app
