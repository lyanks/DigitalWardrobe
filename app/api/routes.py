"""JSON endpoints for the JavaScript on the pages.

A normal route answers with a whole HTML page and the browser loads it.
These answer with a little JSON instead; the page stays where it is and
JavaScript updates just the part that changed.
"""
import io
from datetime import date

from flask import Blueprint, jsonify, render_template, request, send_file
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app.dates import format_date, parse_date
from app.extensions import db
from app.models import Item, Outfit
from app.services import ai
from app.services.autotag import suggest_details
from app.services.combo_check import check_combo
from app.services.images import InvalidImageError, cut_out_preview
from app.services.laundry import wash_notice
from app.services.outfit_rules import outfit_problems
from app.services.planner import ScheduleError, schedule_outfit
from app.services.product_page import FetchError, fetch_product

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
    """{"item_ids": [3, 9], "date": "14.10.2026"} -> {"problems": [...], "combo": ...}

    The builder and the "Log a look" page call this every time you tick a
    box, so you see what's missing before you press Save. Same Python
    rules, no copy in JS. "combo" is idea #1's note ("You wore this combo
    on Wednesday ...") or null; "date" is optional and means today.
    """
    data = request.get_json(silent=True) or {}
    ids = data.get("item_ids")
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        return _error(_("Send a list of item ids."), 400)
    items = db.session.scalars(
        Item.owned_by(current_user.id).where(Item.id.in_(ids))
    ).all()
    if len(items) != len(set(ids)):
        return _error(_("Unknown item."), 404)
    day = parse_date(data.get("date")) or date.today()
    return jsonify(problems=outfit_problems(items), combo=check_combo(current_user.id, items, day))


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
        return _error(_("Send the date as YYYY-MM-DD."), 400)
    if not isinstance(outfit_id, int):
        return _error(_("Send an outfit id."), 400)

    outfit = db.session.scalar(db.select(Outfit).filter_by(id=outfit_id, user_id=current_user.id))
    if outfit is None:
        return _error(_("Unknown outfit."), 404)

    try:
        entry = schedule_outfit(outfit, day, (data.get("note") or "").strip()[:200])
    except ScheduleError as error:
        return _error(str(error), 409)

    return jsonify(
        # "date" for programs (ISO), "date_text" for people (dd.mm.yyyy).
        id=entry.id, date=entry.date.isoformat(), date_text=format_date(entry.date),
        outfit={"id": outfit.id, "name": outfit.name},
        # "You wore this combo on ..." and/or "... is in the wash", or null.
        notice=" ".join(filter(None, [check_combo(current_user.id, outfit.items, day),
                                       wash_notice(outfit.items)])) or None,
        # The same HTML snippet the page uses for an entry, ready to insert.
        html=render_template("planner/_entry.html", entry=entry, today=date.today()),
    ), 201


@bp.route("/fetch-product", methods=["POST"])
def fetch_product_info():
    """{"url": "https://shop.com/shirt"} -> {"name", "price", "currency", "image_url"}.

    The "Fill in from link" button on the wish form calls this. The server
    downloads the page (a browser isn't allowed to read other websites'
    pages from JavaScript), reads it and answers with what it found.
    Any field it couldn't find is null. 422 = nothing found at all.
    """
    url = ((request.get_json(silent=True) or {}).get("url") or "").strip()
    if not url:
        return _error(_("Paste a link first."), 400)
    try:
        return jsonify(fetch_product(url))
    except FetchError as error:
        return _error(str(error), 422)


# ---------- Adding a photo: cut-out preview and AI details ----------
# photo_review.js calls both as soon as you pick a photo, before anything
# is saved. Both read the photo from a normal file upload (multipart form).

def _uploaded_photo():
    photo = request.files.get("photo")
    return photo if photo and photo.filename else None


@bp.route("/photos/cutout", methods=["POST"])
def cutout_preview():
    """photo -> the same photo with its plain background made see-through (PNG).

    Nothing is saved: the browser shows it in the brush editor, you fix
    the edges, and the result comes back with the form when you press Save.
    422 = the background isn't plain enough to cut out this way.
    """
    photo = _uploaded_photo()
    if photo is None:
        return _error(_("Pick a photo first."), 400)
    try:
        cut = cut_out_preview(photo)
    except InvalidImageError as error:
        return _error(str(error), 400)
    if cut is None:
        return _error(_("The background is too busy to remove by itself. "
                        "Use the brush to erase it, or keep the photo as it is."), 422)
    out = io.BytesIO()
    cut.save(out, "PNG")
    out.seek(0)
    return send_file(out, mimetype="image/png")


@bp.route("/photos/details", methods=["POST"])
def photo_details():
    """photo -> {"name", "category_id", "color", "seasons", "styles", "moods", "brand"}.

    The AI looks at the photo and picks from our own lists (services/autotag.py).
    429 = today's limit is used up, 503 = AI is off or didn't answer.
    """
    if not ai.is_enabled():
        return _error(_("AI suggestions are switched off on this server."), 503)
    photo = _uploaded_photo()
    if photo is None:
        return _error(_("Pick a photo first."), 400)
    image_bytes = photo.read()
    try:
        ai.use_quota(current_user.id)
    except ai.AiError as error:
        return _error(str(error), 429)
    try:
        return jsonify(suggest_details(image_bytes))
    except ai.AiError as error:
        return _error(str(error), 503)
    except OSError:  # Pillow couldn't read it (UnidentifiedImageError is an OSError)
        return _error(_("That file is not a readable image."), 400)
