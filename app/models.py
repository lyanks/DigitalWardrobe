from datetime import date, datetime, timezone

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
    # Empty for accounts created with "Sign in with Google".
    password_hash = db.Column(db.String(255))
    # Google's permanent id for this person ("sub"); empty if never linked.
    google_id = db.Column(db.String(255), unique=True)
    display_name = db.Column(db.String(80))
    avatar_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    # One user -> many items. Deleting a user deletes their items too.
    items = db.relationship(
        "Item", back_populates="owner", cascade="all, delete-orphan",
    )
    outfits = db.relationship(
        "Outfit", back_populates="owner", cascade="all, delete-orphan",
    )
    schedule = db.relationship(
        "ScheduledOutfit", back_populates="owner", cascade="all, delete-orphan",
    )

    def set_password(self, password):
        # Store a salted one-way hash, never the password itself.
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False  # Google-only account: no password can match
        return check_password_hash(self.password_hash, password)

    @property
    def has_password(self):
        return self.password_hash is not None

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
    # Your own order in the grid (drag and drop). Smaller = earlier.
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    # relationship() doesn't add a column. It lets you write item.owner
    # and item.category and get objects instead of bare ids.
    owner = db.relationship("User", back_populates="items")
    category = db.relationship("Category", back_populates="items")
    # The rows of the join table that mention this item. Deleting the item
    # deletes those rows, so it simply drops out of its outfits.
    outfit_links = db.relationship(
        "OutfitItem", back_populates="item", cascade="all, delete-orphan",
    )

    @property
    def outfits(self):
        return [link.outfit for link in self.outfit_links]

    def __repr__(self):
        return f"<Item {self.name!r} of user {self.user_id}>"


class Outfit(db.Model):
    """A named combination of items, e.g. "Monday office"."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    occasion = db.Column(db.String(50))
    notes = db.Column(db.Text)
    # Optional photo of you wearing the whole outfit.
    image_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    owner = db.relationship("User", back_populates="outfits")
    # order_by: outfit.item_links always comes back in display order.
    # Deleting the outfit deletes its links, never the items themselves.
    item_links = db.relationship(
        "OutfitItem", back_populates="outfit", cascade="all, delete-orphan",
        order_by="OutfitItem.position",
    )
    # Every day this outfit is planned for. Deleting the outfit removes them.
    schedule = db.relationship(
        "ScheduledOutfit", back_populates="outfit", cascade="all, delete-orphan",
        order_by="ScheduledOutfit.date",
    )

    @property
    def items(self):
        return [link.item for link in self.item_links]

    def __repr__(self):
        return f"<Outfit {self.name!r} of user {self.user_id}>"


class OutfitItem(db.Model):
    """The join table between Outfit and Item (many-to-many).

    One row = "this item is in this outfit". An outfit has many items and an
    item can be in many outfits; neither table could hold that on its own.
    The two ids together are the primary key, so the same item can't be
    added to the same outfit twice.
    """

    outfit_id = db.Column(db.Integer, db.ForeignKey("outfit.id"), primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), primary_key=True, index=True)
    # Where the item is shown in the outfit (top to bottom). Smaller = earlier.
    position = db.Column(db.Integer, nullable=False, default=0)

    outfit = db.relationship("Outfit", back_populates="item_links")
    item = db.relationship("Item", back_populates="outfit_links")


class ScheduledOutfit(db.Model):
    """One outfit planned for one day: an entry in the calendar.

    A day can have several (day + evening), but the same outfit only once
    per day: the UniqueConstraint below makes the database refuse a repeat.
    """

    __table_args__ = (
        db.UniqueConstraint("outfit_id", "date", name="uq_scheduled_outfit_outfit_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    outfit_id = db.Column(db.Integer, db.ForeignKey("outfit.id"), nullable=False)
    # db.Date stores only the day (2026-10-14), no time and no time zone.
    date = db.Column(db.Date, nullable=False, index=True)
    note = db.Column(db.String(200))
    worn = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    owner = db.relationship("User", back_populates="schedule")
    outfit = db.relationship("Outfit", back_populates="schedule")

    @property
    def can_be_worn(self):
        """You can only say you wore something today or earlier."""
        return self.date <= date.today()

    def set_worn(self, worn):
        """Mark worn (or not) and keep every item's times_worn in step.

        This is the only place times_worn changes, so the counter can't
        drift: +1 per item when ticked, -1 when unticked.
        """
        if worn == self.worn:
            return
        step = 1 if worn else -1
        for item in self.outfit.items:
            item.times_worn = max(0, item.times_worn + step)
        self.worn = worn

    def __repr__(self):
        return f"<ScheduledOutfit {self.outfit_id} on {self.date}>"
