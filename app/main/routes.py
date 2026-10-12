from flask import Blueprint, current_app, render_template, send_from_directory
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Item
from app.services.planner import coming_week

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    recent, total, week = [], 0, []
    if current_user.is_authenticated:
        week = coming_week(current_user.id)
        mine = db.select(Item).filter_by(user_id=current_user.id)
        recent = db.session.scalars(mine.order_by(Item.created_at.desc()).limit(4)).all()
        total = db.session.scalar(db.select(db.func.count()).select_from(mine.subquery()))
    return render_template("index.html", title="Home", recent=recent, total=total, week=week)


@bp.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    # uploads/ is outside static/, so Flask doesn't serve it automatically.
    # send_from_directory refuses paths like "../config.py", so users can
    # only ever get files that are inside the uploads folder.
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
