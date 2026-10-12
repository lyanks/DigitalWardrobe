from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    """One row in the `user` table = one account.

    UserMixin adds what Flask-Login expects from a user object:
    is_authenticated, is_active, get_id() ...
    """

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(80))
    avatar_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    def set_password(self, password):
        # Store a salted one-way hash, never the password itself.
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def shown_name(self):
        """The name to show on pages: display name if set, else username."""
        return self.display_name or self.username

    def __repr__(self):
        return f"<User {self.username}>"


@login_manager.user_loader
def load_user(user_id):
    # Flask-Login keeps only the user's id in the session cookie.
    # On every request it calls this to turn that id back into a User.
    return db.session.get(User, int(user_id))
