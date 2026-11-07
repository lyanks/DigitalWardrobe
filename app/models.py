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
    # "en" or "uk" (app/i18n.py). Empty = follow the browser.
    language = db.Column(db.String(5))
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
    # Idea #1: what they actually wore, day by day.
    wear_logs = db.relationship("WearLog", back_populates="owner", cascade="all, delete-orphan")
    trips = db.relationship("Trip", back_populates="owner", cascade="all, delete-orphan")
    # Saved inspiration (Pinterest pins and other pictures), newest first.
    ideas = db.relationship("Idea", back_populates="owner", cascade="all, delete-orphan",
                            order_by="Idea.created_at.desc()")

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
    """A list shared by everyone (Tops, Bottoms, ...). Filled by seed.py,
    and changed by the admin on /admin/options."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    # Where it goes on the body: top, bottom, full, outer, feet, accessory.
    slot = db.Column(db.String(20), nullable=False)
    # Shown in Ukrainian. Empty = the translation in messages.po, if any.
    name_uk = db.Column(db.String(50))
    position = db.Column(db.Integer, nullable=False, default=0)
    # Hidden = can't be picked for new items; old items keep it.
    hidden = db.Column(db.Boolean, nullable=False, default=False)

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
    # Seasons, styles and moods: you can pick several of each, so they live
    # in their own table (ItemTag), one row per choice.
    tags = db.relationship("ItemTag", back_populates="item", cascade="all, delete-orphan")

    def tag_values(self, kind):
        """["winter", "autumn"]: this item's choices of one kind."""
        return [tag.value for tag in self.tags if tag.kind == kind]

    def set_tags(self, kind, values):
        """Replace the item's choices of one kind with `values`."""
        keep = [tag for tag in self.tags if tag.kind != kind]
        unique = list(dict.fromkeys(values))  # drops repeats, keeps the order
        self.tags = keep + [ItemTag(kind=kind, value=value) for value in unique]

    @property
    def seasons(self):
        """An empty list means "all seasons"."""
        return self.tag_values("season")

    @property
    def styles(self):
        return self.tag_values("style")

    @property
    def moods(self):
        return self.tag_values("mood")

    def fits_season(self, season):
        """True if you can wear it in that season ("all"-season items always fit)."""
        return not self.seasons or season in self.seasons

    @classmethod
    def tagged(cls, kind, value):
        """A WHERE condition: "this item has the tag". Use it in queries:
        Item.owned_by(1).where(Item.tagged("mood", "home"))."""
        return cls.tags.any(kind=kind, value=value)

    @classmethod
    def in_season(cls, season):
        """WHERE condition: tagged with the season, or no season at all (all year)."""
        return cls.tagged("season", season) | ~cls.tags.any(kind="season")

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


class ItemTag(db.Model):
    """One season, style or mood picked for an item.

    A coat for "autumn" and "winter" has two rows here:
    (7, "season", "autumn") and (7, "season", "winter").
    The three columns together are the primary key, so the same choice
    can't be saved twice. `value` is the English word from the Option table,
    like Item.color.
    """

    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), primary_key=True)
    kind = db.Column(db.String(10), primary_key=True)  # season, style, mood
    value = db.Column(db.String(30), primary_key=True, index=True)

    item = db.relationship("Item", back_populates="tags")

    def __repr__(self):
        return f"<ItemTag {self.kind}={self.value!r} on item {self.item_id}>"


class Outfit(db.Model):
    """A named combination of items, e.g. "Monday office"."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    occasion = db.Column(db.String(50))
    notes = db.Column(db.Text)
    # Optional photo of you wearing the whole outfit.
    image_path = db.Column(db.String(255))
    # Optional: the saved idea (a pin) this outfit recreates.
    idea_id = db.Column(db.Integer, db.ForeignKey("idea.id"), index=True)
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
    idea = db.relationship("Idea", back_populates="outfits")

    @property
    def items(self):
        return [link.item for link in self.item_links]

    @property
    def moods(self):
        """The moods every item of the outfit shares, e.g. ["comfortable"].

        Worked out from the items, so there's nothing extra to fill in.
        Items without a mood are skipped, so one plain belt doesn't
        cancel the outfit's mood.
        """
        with_mood = [item.moods for item in self.items if item.moods]
        if not with_mood:
            return []
        return [mood for mood in with_mood[0] if all(mood in moods for moods in with_mood)]

    @property
    def board(self):
        """[(item, position), ...] for the outfit board, back to front."""
        from app.services.outfit_board import board_pieces  # here, to avoid a circular import
        return board_pieces(self.item_links)

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
    # Its place on the outfit board (services/outfit_board.py), in % of the
    # board: x and y are the left and top edge, width is the picture's width
    # (its height follows the photo). layer: higher numbers sit on top.
    # Empty (None) = never arranged: the board puts it in its slot's spot.
    board_x = db.Column(db.Float)
    board_y = db.Column(db.Float)
    board_width = db.Column(db.Float)
    board_layer = db.Column(db.Integer)

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


class Option(db.Model):
    """One choice in a shared list: a colour, season, style, mood or occasion.

    Items store the English `value` itself ("light blue"), not this row's
    id, so the lists could move here from code without touching any item.
    The admin changes them on /admin/options.
    """

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False)  # color, season, style, mood, occasion
    value = db.Column(db.String(30), nullable=False)
    name_uk = db.Column(db.String(50))  # empty = the translation in messages.po, if any
    hex = db.Column(db.String(120))  # colours only: the dot ("#3b6fd1" or a gradient)
    position = db.Column(db.Integer, nullable=False, default=0)
    hidden = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (db.UniqueConstraint("kind", "value"),)


class InviteCode(db.Model):
    """A one-time code someone needs to create an account.

    A code is usable while it isn't used, turned off or past its expiry
    date. When someone signs up with it, used_at and used_by are filled in,
    so the admin page can show who joined with which code.
    """

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    note = db.Column(db.String(100))  # who it's for, e.g. "for Olena"
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    expires_on = db.Column(db.Date)  # last day it works; empty = never expires
    disabled_at = db.Column(db.DateTime(timezone=True))
    used_at = db.Column(db.DateTime(timezone=True))
    used_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    used_by = db.relationship("User")

    def status(self, today):
        """One of "used", "off", "expired", "waiting"."""
        if self.used_at:
            return "used"
        if self.disabled_at:
            return "off"
        if self.expires_on and self.expires_on < today:
            return "expired"
        return "waiting"


class GoalAnswer(db.Model):
    """One tick in "Why do you use Digital Wardrobe?" (setup wizard, step 2).

    Anonymous on purpose: no user_id and no time, so nobody can tell who
    picked what. It's only for counting: "how many people want to buy
    less?" is one GROUP BY (see `flask goals`). Someone who ticks two
    reasons adds two rows.
    """

    id = db.Column(db.Integer, primary_key=True)
    goal = db.Column(db.String(20), nullable=False, index=True)  # a key of app/goals.py GOALS


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


class Idea(db.Model):
    """A saved inspiration picture: a Pinterest pin, or any photo you upload.

    The picture is copied to uploads/ideas/ (image_path) when the server
    can download it. If it can't (PythonAnywhere's free plan only reaches
    allow-listed sites), image_url keeps the picture's web address and the
    page shows it straight from there.
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    source_url = db.Column(db.String(500))   # the pin (or page) it came from
    image_url = db.Column(db.String(1000))   # the picture on the web
    image_path = db.Column(db.String(255))   # our own copy in uploads/
    title = db.Column(db.String(200))
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    owner = db.relationship("User", back_populates="ideas")
    # Outfits made after this idea. No cascade: deleting the idea keeps the
    # outfits, SQLAlchemy just empties their idea_id.
    outfits = db.relationship("Outfit", back_populates="idea")

    def __repr__(self):
        return f"<Idea {self.id} of user {self.user_id}>"


class AiUsage(db.Model):
    """How many AI requests a user made on one day (for the daily limit).

    One row per user per day: (3, 07.11.2026, 12). Old rows are harmless;
    they also show how much the AI is used.
    """

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    day = db.Column(db.Date, primary_key=True)
    count = db.Column(db.Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<AiUsage user {self.user_id} on {self.day}: {self.count}>"
