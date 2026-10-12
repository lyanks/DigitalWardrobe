"""JSON endpoints for the JavaScript on the pages.

A normal route answers with a whole HTML page and the browser loads it.
These answer with a little JSON instead; the page stays where it is and
JavaScript updates just the part that changed.
"""
from datetime import date

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app.dates import format_date
from app.extensions import db
from app.models import Item, Outfit
from app.services.outfit_rules import outfit_problems
from app.services.planner import ScheduleError, schedule_outfit

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.before_request
@login_required
def require_login():
    """Same rule as the pages: log in first."""


def _error(message, status):
    # Errors are JSON too, so the JavaScript can show the message.
    return jsonify(error=message), status


@bp.route("/outfits/check", methods=["POST"])
def check_outfit():
    """{"item_ids": [3, 9]} -> {"problems": [...]}: the outfit rules, live.

    The builder calls this every time you tick a box, so you see what's
    missing before you press Save. Same Python rules, no copy in JS.
    """
    ids = (request.get_json(silent=True) or {}).get("item_ids")
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        return _error("Send a list of item ids.", 400)
    items = db.session.scalars(
        db.select(Item).where(Item.id.in_(ids), Item.user_id == current_user.id)
    ).all()
    if len(items) != len(set(ids)):
        return _error("Unknown item.", 404)
    return jsonify(problems=outfit_problems(items))


@bp.route("/schedule", methods=["POST"])
def schedule():
    """{"outfit_id": 4, "date": "2026-10-14"} -> the new calendar entry.

    calendar.js calls this when you drop an outfit on a day.
    Status codes say what happened: 201 created, 400 bad input,
    404 not your outfit, 409 already planned that day.
    """
    data = request.get_json(silent=True) or {}
    outfit_id = data.get("outfit_id")
    try:
        day = date.fromisoformat(data.get("date", ""))
    except (TypeError, ValueError):
        return _error("Send the date as YYYY-MM-DD.", 400)
    if not isinstance(outfit_id, int):
        return _error("Send an outfit id.", 400)

    outfit = db.session.scalar(db.select(Outfit).filter_by(id=outfit_id, user_id=current_user.id))
    if outfit is None:
        return _error("Unknown outfit.", 404)

    try:
        entry = schedule_outfit(outfit, day, (data.get("note") or "").strip()[:200])
    except ScheduleError as error:
        return _error(str(error), 409)

    return jsonify(
        # "date" for programs (ISO), "date_text" for people (dd.mm.yyyy).
        id=entry.id, date=entry.date.isoformat(), date_text=format_date(entry.date),
        outfit={"id": outfit.id, "name": outfit.name},
        # The same HTML snippet the page uses for an entry, ready to insert.
        html=render_template("planner/_entry.html", entry=entry, today=date.today()),
    ), 201
