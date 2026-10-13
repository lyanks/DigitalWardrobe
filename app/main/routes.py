from datetime import date, timedelta

from flask import Blueprint, current_app, render_template, send_from_directory
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Item, Outfit, WearLog
from app.services.planner import coming_week
from app.services.stats import not_worn_lately, wardrobe_stats
from app.services.trips import trip_for_each_day, trips_between

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if not current_user.is_authenticated:
        return render_template("index.html", title="Home")

    week = coming_week(current_user.id)
    trips = trip_for_each_day(
        trips_between(current_user.id, week[0][0], week[-1][0]), [day for day, _ in week]
    )
    forgotten = not_worn_lately(current_user.id, limit=4)
    mine = Item.owned_by(current_user.id)
    recent = db.session.scalars(mine.order_by(Item.created_at.desc()).limit(4)).all()

    def count(query):
        """SELECT COUNT(*) FROM (the query)."""
        return db.session.scalar(db.select(db.func.count()).select_from(query.subquery()))

    # The three big numbers on the home page.
    numbers = {
        "items": count(mine),
        "outfits": count(db.select(Outfit).filter_by(user_id=current_user.id)),
        # Days in the last week you logged or ticked a look as worn.
        "worn_days": db.session.scalar(
            db.select(db.func.count(db.distinct(WearLog.date)))
            .where(WearLog.user_id == current_user.id,
                   WearLog.date > date.today() - timedelta(days=7))
        ),
    }
    return render_template("index.html", title="Home", recent=recent, week=week, trips=trips,
                           forgotten=forgotten, numbers=numbers, today=date.today())


@bp.route("/stats")
@login_required
def stats():
    return render_template("stats.html", title="Stats", stats=wardrobe_stats(current_user.id))


@bp.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    # uploads/ is outside static/, so Flask doesn't serve it automatically.
    # send_from_directory refuses paths like "../config.py", so users can
    # only ever get files that are inside the uploads folder.
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
