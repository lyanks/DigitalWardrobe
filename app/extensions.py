"""Extension objects, created once and shared by the whole app.

They are created here *without* an app and connected to it later in
create_app() with init_app(). That way models.py and the blueprints can
import `db` without importing the app itself (no circular imports).
"""
from authlib.integrations.flask_client import OAuth
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
oauth = OAuth()  # "Sign in with Google"

login_manager = LoginManager()
# Where @login_required sends visitors who are not logged in.
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to see that page."
login_manager.login_message_category = "info"
