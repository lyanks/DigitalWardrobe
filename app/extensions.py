"""Extension objects, created once and shared by the whole app.

They are created here *without* an app and connected to it later in
create_app() with init_app(). That way models.py and the blueprints can
import `db` without importing the app itself (no circular imports).
"""
from authlib.integrations.flask_client import OAuth
from flask import g, has_app_context
from flask_babel import Babel, lazy_gettext as _l
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.session import Session
from flask_wtf import CSRFProtect


class GuestAwareSession(Session):
    """db.session, with one switch for guest mode (app/guests.py).

    Every read and write in the app asks get_bind() which database to use.
    During a guest's request, g.guest_engine is that guest's own throwaway
    database file, so the answer is that file and never wardrobe.db.
    Because it's this one place, no route can forget it.
    """

    def get_bind(self, mapper=None, clause=None, bind=None, **kwargs):
        if bind is None and has_app_context():
            guest_engine = g.get("guest_engine")
            if guest_engine is not None:
                return guest_engine
        return super().get_bind(mapper=mapper, clause=clause, bind=bind, **kwargs)


db = SQLAlchemy(session_options={"class_": GuestAwareSession})
migrate = Migrate()
csrf = CSRFProtect()
oauth = OAuth()  # "Sign in with Google"
babel = Babel()  # English / Ukrainian (app/i18n.py)

login_manager = LoginManager()
# Where @login_required sends visitors who are not logged in.
login_manager.login_view = "auth.login"
login_manager.login_message = _l("Please log in to see that page.")
login_manager.login_message_category = "info"
