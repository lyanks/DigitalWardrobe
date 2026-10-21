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
    # Idea #5: how the app looks for this user (see app/themes.py).
    theme = db.Column(db.String(20), nullable=False, default="midnight",
                      server_default="midnight")
    accent_color = db.Column(db.String(7))  # "#c4a8ff", or None = the theme's own
    # Idea #7: when the setup wizard was finished (or skipped). Empty = not yet.
    onboarded_at = db.Column(db.DateTime(timezone=True))
    # When they opened the tutorial or closed its banner. Empty = suggest it.
    tutorial_seen_at = db.Column(db.DateTime(timezone=True))
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
    # Idea #7: why they use the app. A list of UserGoal rows.
    goals = db.relationship("UserGoal", cascade="all, delete-orphan")
    # Idea #1: what they actually wore, day by day.
    wear_logs = db.relationship("WearLog", back_populates="owner", cascade="all, delete-orphan")
    trips = db.relationship("Trip", back_populates="owner", cascade="all, delete-orphan")

    @property
    def goal_keys(self):
        return [goal.goal for goal in self.goals]

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


OWNED = "owned"
WISHLIST = "wishlist"


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
    # "owned" = in your wardrobe, "wishlist" = you want it but don't have it
    # yet. server_default fills "owned" into rows that existed before.
    status = db.Column(db.String(10), nullable=False, default="owned",
                       server_default="owned", index=True)
    # Wishlist extras, all optional (a vague wish has none of them).
    shop_url = db.Column(db.String(500))
    # Numeric(10, 2): an exact decimal with 2 digits after the point.
    # Never use Float for money: 0.1 + 0.2 is 0.30000000000000004 there.
    price = db.Column(db.Numeric(10, 2))
    currency = db.Column(db.String(3))
    priority = db.Column(db.Integer)  # 1 = must have, 2 = would be nice, 3 = someday
    # Laundry: the day it went in the wash, or None when it's clean.
    # A date instead of True/False, so the page can say "since Monday".
    washing_since = db.Column(db.Date)
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
    # Same idea for the wear log: a deleted item leaves the days it was worn.
    wear_links = db.relationship(
        "WearLogItem", back_populates="item", cascade="all, delete-orphan",
    )
    # ...and for suitcases: a deleted item is taken out of every trip.
    trip_links = db.relationship(
        "TripItem", back_populates="item", cascade="all, delete-orphan",
    )

    @property
    def outfits(self):
        return [link.outfit for link in self.outfit_links]

    @property
    def is_wish(self):
        return self.status == WISHLIST

    @property
    def in_wash(self):
        return self.washing_since is not None

    @classmethod
    def owned_by(cls, user_id):
        """SELECT the clothes a user actually owns (not their wishlist).

        The wardrobe grid, the outfit builder, the home page and the stats
        all start from here, so a wish can never sneak into an outfit.
        """
        return db.select(cls).where(cls.user_id == user_id, cls.status == OWNED)

    @classmethod
    def wished_by(cls, user_id):
        """SELECT a user's wishlist."""
        return db.select(cls).where(cls.user_id == user_id, cls.status == WISHLIST)

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
    # Days this outfit was worn. No cascade: deleting the outfit keeps those
    # days in the log (you did wear the clothes), SQLAlchemy just empties
    # their outfit_id.
    wear_logs = db.relationship("WearLog", back_populates="outfit")

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
        """Mark worn (or not), and add (or remove) the day in the wear log.

        The wear log keeps every item's times_worn in step (see WearLog), so
        ticking adds one wear per item and unticking takes it back.
        """
        if worn == self.worn:
            return
        if worn:
            WearLog.record(self.user_id, self.date, self.outfit.items, outfit=self.outfit)
        else:
            log = db.session.scalar(db.select(WearLog).filter_by(
                user_id=self.user_id, outfit_id=self.outfit_id, date=self.date))
            if log is not None:
                log.undo()
        self.worn = worn

    def __repr__(self):
        return f"<ScheduledOutfit {self.outfit_id} on {self.date}>"


class UserGoal(db.Model):
    """One reason a user picked in the setup wizard, e.g. "buy_less".

    A user can pick several, so they get their own small table (one user ->
    many rows) instead of one column. That also makes them easy to count:
    "how many people use the app to buy less?" is one GROUP BY.
    """

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    goal = db.Column(db.String(20), primary_key=True)  # a key of app/goals.py GOALS


class WearLog(db.Model):
    """Idea #1: one day's look, the clothes you actually wore.

    Two ways in: ticking "Mark worn" on a planned outfit (outfit_id is
    filled), or "Log a look" with loose items (outfit_id stays empty).
    Either way the items end up in the same place, so "what did I wear on
    Wednesday?" is one query.
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    outfit_id = db.Column(db.Integer, db.ForeignKey("outfit.id"))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    owner = db.relationship("User", back_populates="wear_logs")
    outfit = db.relationship("Outfit", back_populates="wear_logs")
    item_links = db.relationship("WearLogItem", back_populates="log", cascade="all, delete-orphan")

    @property
    def items(self):
        return [link.item for link in self.item_links]

    @classmethod
    def record(cls, user_id, day, items, outfit=None):
        """Log that these items were worn on `day`. Each counts one more wear.

        Together with undo() this is the only place times_worn changes, so
        the counter can't drift from the log.
        """
        log = cls(user_id=user_id, date=day, outfit=outfit,
                  item_links=[WearLogItem(item=item) for item in items])
        for item in items:
            item.times_worn = (item.times_worn or 0) + 1
        db.session.add(log)
        return log

    def undo(self):
        """Take the day back out of the log, and its wears off the items."""
        for item in self.items:
            item.times_worn = max(0, item.times_worn - 1)
        db.session.delete(self)

    def __repr__(self):
        return f"<WearLog of user {self.user_id} on {self.date}>"


class WearLogItem(db.Model):
    """The join table between WearLog and Item, like OutfitItem."""

    wear_log_id = db.Column(db.Integer, db.ForeignKey("wear_log.id"), primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), primary_key=True, index=True)

    log = db.relationship("WearLog", back_populates="item_links")
    item = db.relationship("Item", back_populates="wear_links")


class Trip(db.Model):
    """A trip with a suitcase: from start_date to end_date (both included)."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    owner = db.relationship("User", back_populates="trips")
    item_links = db.relationship("TripItem", back_populates="trip", cascade="all, delete-orphan",
                                 order_by="TripItem.added_at")

    @property
    def days(self):
        """How many days, counting both ends: 14.10 to 16.10 is 3 days."""
        return (self.end_date - self.start_date).days + 1

    @property
    def packed_count(self):
        return sum(1 for link in self.item_links if link.packed)

    def covers(self, day):
        return self.start_date <= day <= self.end_date

    def __repr__(self):
        return f"<Trip {self.name!r} {self.start_date}..{self.end_date}>"


class TripItem(db.Model):
    """One item in a trip's suitcase. `packed` = actually in the bag yet."""

    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), primary_key=True, index=True)
    packed = db.Column(db.Boolean, nullable=False, default=False)
    added_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    trip = db.relationship("Trip", back_populates="item_links")
    item = db.relationship("Item", back_populates="trip_links")
