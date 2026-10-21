"""Guest mode: try the whole app without an account, saving nothing.

How a guest's data is kept apart from real data:

1. "Try as guest" makes a brand-new database file just for this visitor,
   in a temporary folder outside the project: <GUEST_FOLDER>/<id>.db, and
   a folder <GUEST_FOLDER>/<id>/ for their photos.
2. The random id goes into the session cookie. Flask signs that cookie
   with SECRET_KEY, so nobody can change it to point somewhere else.
3. switch() runs before every request. If the cookie has a guest id, it
   sets g.guest_engine, and db.session (GuestAwareSession in
   extensions.py) then uses that file for everything. wardrobe.db is
   never touched.
4. Leave, or 1 hour without any request, and the file and photos are
   deleted. clean_up() runs on requests, at most once a minute.
"""
import os
import secrets
import shutil
import tempfile
import time
from datetime import date, timedelta

from flask import current_app, flash, g, redirect, request, session, url_for
from flask_babel import gettext as _
from flask_login import login_user
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.extensions import db

IDLE_SECONDS = 60 * 60   # deleted after 1 hour without a request
MAX_GUESTS = 50          # at once; the longest-idle one is cleared first
MAX_PHOTOS = 20          # per guest, so the free disk doesn't fill up

_engines = {}            # guest id -> SQLAlchemy engine (one file each)
_last_clean_up = 0.0


def folder():
    path = current_app.config.get("GUEST_FOLDER") or os.path.join(
        tempfile.gettempdir(), "digitalwardrobe-guests")
    os.makedirs(path, exist_ok=True)
    return path


def _db_path(guest_id):
    return os.path.join(folder(), f"{guest_id}.db")


def _upload_path(guest_id):
    return os.path.join(folder(), guest_id)


def _engine(guest_id):
    if guest_id not in _engines:
        # NullPool: no connection stays open, so the file can be deleted.
        _engines[guest_id] = create_engine(f"sqlite:///{_db_path(guest_id)}", poolclass=NullPool)
    return _engines[guest_id]


def is_guest():
    """True during a guest's request."""
    return g.get("guest_engine") is not None


def upload_folder():
    """Where photos go: the guest's own folder, or the real uploads folder."""
    return g.get("guest_uploads") or current_app.config["UPLOAD_FOLDER"]


def photo_count():
    count = 0
    for _root, _dirs, files in os.walk(g.guest_uploads):
        count += len(files)
    return count


# ---------- every request ----------

def switch():
    """before_request: point db.session at the guest's file, if this is a guest."""
    clean_up()
    guest_id = session.get("guest_id")
    if not guest_id:
        return None
    path = _db_path(guest_id)
    if not _is_valid_id(guest_id) or not os.path.exists(path):
        # Deleted after an hour of nothing, or by Leave in another tab.
        _forget_session()
        flash(_("Your guest visit has ended, so everything you added is gone."), "info")
        return redirect(url_for("main.index"))
    os.utime(path)  # "still here": resets the 1-hour clock
    db.session.close()  # start clean, nothing from a real-database query
    g.guest_engine = _engine(guest_id)
    g.guest_uploads = _upload_path(guest_id)
    return None


def finish(_error=None):
    """teardown_request: let go of the guest's database again."""
    if g.pop("guest_engine", None) is not None:
        g.pop("guest_uploads", None)
        db.session.close()


def _is_valid_id(guest_id):
    return isinstance(guest_id, str) and len(guest_id) == 32 and guest_id.isalnum()


def _forget_session():
    """Log the guest out without loading any user (no database involved)."""
    language = session.get("language")
    session.clear()
    if language:
        session["language"] = language


# ---------- start and leave ----------

def start():
    """Make the guest's database, fill it, and log them in."""
    from app.models import Category, Option, User, utcnow

    _make_room()
    guest_id = secrets.token_hex(16)
    engine = _engine(guest_id)
    db.metadata.create_all(engine)
    os.makedirs(_upload_path(guest_id), exist_ok=True)

    # The shared lists come from the real database, so guests see the
    # options the admin set up. Copied as plain values, nothing else.
    categories = db.session.scalars(db.select(Category)).all()
    options = db.session.scalars(db.select(Option)).all()
    with Session(engine) as guest_db:
        for c in categories:
            guest_db.add(Category(id=c.id, name=c.name, slot=c.slot, name_uk=c.name_uk,
                                  position=c.position, hidden=c.hidden))
        for o in options:
            guest_db.add(Option(kind=o.kind, value=o.value, name_uk=o.name_uk, hex=o.hex,
                                position=o.position, hidden=o.hidden))
        guest = User(username="guest", email=f"{guest_id}@guest.invalid",
                     display_name=_("Guest"), language=session.get("language"),
                     onboarded_at=utcnow())
        guest_db.add(guest)
        guest_db.flush()
        guest_user_id = guest.id
        _add_samples(guest_db, guest_user_id, categories)
        guest_db.commit()

    _forget_session()
    session["guest_id"] = guest_id
    g.guest_engine = engine
    g.guest_uploads = _upload_path(guest_id)
    db.session.close()
    login_user(db.session.get(User, guest_user_id))


def leave(keep_session=False):
    """Delete everything of this guest and log them out.

    keep_session=True only takes the guest out of the session and keeps
    the rest (used while a Google login is in the middle of its steps).
    """
    guest_id = session.get("guest_id")
    finish()
    if keep_session:
        session.pop("guest_id", None)
        session.pop("_user_id", None)
    else:
        _forget_session()
    if guest_id and _is_valid_id(guest_id):
        _delete(guest_id)


def _delete(guest_id):
    engine = _engines.pop(guest_id, None)
    if engine is not None:
        engine.dispose()
    if os.path.exists(_db_path(guest_id)):
        os.remove(_db_path(guest_id))
    shutil.rmtree(_upload_path(guest_id), ignore_errors=True)


def _guest_files():
    """[(last used, guest id), ...] oldest first."""
    found = []
    for name in os.listdir(folder()):
        if name.endswith(".db"):
            path = os.path.join(folder(), name)
            found.append((os.path.getmtime(path), name[:-3]))
    return sorted(found)


def clean_up(force=False):
    """Delete every guest idle for an hour. Runs at most once a minute."""
    global _last_clean_up
    now = time.time()
    if not force and now - _last_clean_up < 60:
        return
    _last_clean_up = now
    for last_used, guest_id in _guest_files():
        if now - last_used > IDLE_SECONDS:
            _delete(guest_id)


def _make_room():
    """Keep at most MAX_GUESTS - 1 before adding one more."""
    guests = _guest_files()
    while len(guests) >= MAX_GUESTS:
        _delete(guests.pop(0)[1])


# ---------- a small sample wardrobe ----------

def _add_samples(guest_db, user_id, categories):
    """A few clothes and two outfits, so a visitor sees something at once."""
    from app.models import Item, Outfit, OutfitItem, ScheduledOutfit

    slots = {c.name: c.id for c in categories}

    def category(name):
        # The admin may have renamed or removed one: fall back to the first.
        return slots.get(name) or categories[0].id

    # The names are saved in the language the guest has right now.
    samples = [
        (_("White T-shirt"), "Tops", "white", "casual", 12),
        (_("Striped shirt"), "Tops", "navy", "classic", 5),
        (_("Blue jeans"), "Bottoms", "blue", "casual", 15),
        (_("Black trousers"), "Bottoms", "black", "business", 7),
        (_("Beige trench coat"), "Outerwear", "beige", "classic", 4),
        (_("White sneakers"), "Shoes", "white", "sporty", 18),
        (_("Black boots"), "Shoes", "black", "classic", 6),
        (_("Red scarf"), "Accessories", "red", "casual", 0),
    ]
    items = []
    for position, (name, cat, color, style, worn) in enumerate(samples):
        item = Item(user_id=user_id, category_id=category(cat), name=name, color=color,
                    style=style, season="all", times_worn=worn, position=position)
        guest_db.add(item)
        items.append(item)
    items[1].washing_since = date.today()  # one in the wash, to show laundry
    guest_db.flush()

    looks = [(_("Weekend"), "casual", [0, 2, 5]), (_("Office"), "work", [1, 3, 6, 4])]
    outfits = []
    for name, occasion, picks in looks:
        outfit = Outfit(user_id=user_id, name=name, occasion=occasion)
        guest_db.add(outfit)
        guest_db.flush()
        for position, index in enumerate(picks):
            guest_db.add(OutfitItem(outfit_id=outfit.id, item_id=items[index].id, position=position))
        outfits.append(outfit)
    guest_db.add(ScheduledOutfit(user_id=user_id, outfit_id=outfits[1].id,
                                 date=date.today() + timedelta(days=1)))


# ---------- routes ----------

def register_routes(app):
    from flask import Blueprint

    bp = Blueprint("guest", __name__, url_prefix="/guest")

    @bp.route("", methods=["POST"])
    def try_it():
        from flask_login import current_user
        if current_user.is_authenticated and not is_guest():
            return redirect(url_for("main.index"))
        if is_guest():
            leave()
        start()
        # No message: the guest bar on every page already says it.
        return redirect(url_for("main.index"))

    @bp.route("/leave", methods=["POST"])
    def leave_route():
        leave()
        flash(_("Guest visit ended. Everything you added is deleted."), "info")
        target = request.form.get("next")
        return redirect(url_for("auth.register") if target == "register" else url_for("main.index"))

    app.register_blueprint(bp)
    app.before_request(switch)
    app.teardown_request(finish)
