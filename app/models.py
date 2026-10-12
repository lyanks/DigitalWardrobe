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

    # One user -> many items. Deleting a user deletes their items too.
    items = db.relationship(
        "Item", back_populates="owner", cascade="all, delete-orphan",
    )

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


class Category(db.Model):
    """A fixed list shared by everyone (Tops, Bottoms, ...). Filled by seed.py."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    # Where it goes on the body: top, bottom, full, outer, feet, accessory.
    slot = db.Column(db.String(20), nullable=False)

    items = db.relationship("Item", back_populates="category")

    def __repr__(self):
        return f"<Category {self.name}>"


class Item(db.Model):
    """One piece of clothing, owned by one user."""

    id = db.Column(db.Integer, primary_key=True)
    # ForeignKey = "this number must be the id of a row in that table".
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)

    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(30), nullable=False)
    brand = db.Column(db.String(60))
    size = db.Column(db.String(20))
    season = db.Column(db.String(20), nullable=False, default="all")
    style = db.Column(db.String(30))
    purchase_date = db.Column(db.Date)
    image_path = db.Column(db.String(255))
    notes = db.Column(db.Text)
    times_worn = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    # relationship() doesn't add a column. It lets you write item.owner
    # and item.category and get objects instead of bare ids.
    owner = db.relationship("User", back_populates="items")
    category = db.relationship("Category", back_populates="items")

    def __repr__(self):
        return f"<Item {self.name!r} of user {self.user_id}>"
