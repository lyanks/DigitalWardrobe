"""Trips and their suitcases: plan the dates, then drag clothes in.

The pack page works in two ways:
- Plain forms: every "+", "×" and "packed" button is a small POST form,
  so it works on any phone and without JavaScript.
- static/js/suitcase.js adds drag and drop on top. It sends the same
  requests with fetch() and asks for JSON (Accept: application/json),
  so the page doesn't reload. The routes answer whichever was asked for.
"""
from datetime import date

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_babel import ngettext
from flask_login import current_user, login_required

from app.dates import format_date
from app.extensions import db
from app.models import Item, Outfit, Trip, TripItem
from app.outfits.routes import my_items_by_category
from app.trips.forms import TripForm

bp = Blueprint("trips", __name__, url_prefix="/trips")


@bp.before_request
@login_required
def require_login():
    """Suitcases are private too."""


def get_own_trip_or_404(trip_id):
    trip = db.session.scalar(db.select(Trip).filter_by(id=trip_id, user_id=current_user.id))
    if trip is None:
        abort(404)
    return trip


def wants_json():
    """True when suitcase.js asked (fetch with Accept: application/json)."""
    return request.accept_mimetypes.best_match(["application/json", "text/html"]) == "application/json"


def _counts(trip):
    return {"count": len(trip.item_links), "packed": trip.packed_count}


def _back(trip):
    return redirect(url_for("trips.pack", trip_id=trip.id))


# ---------- List and create ----------

@bp.route("", methods=["GET", "POST"])
def index():
    form = TripForm()
    if form.validate_on_submit():
        trip = Trip(user_id=current_user.id, name=form.name.data.strip(),
                    start_date=form.start_date.data, end_date=form.end_date.data)
        db.session.add(trip)
        db.session.commit()
        flash(_("Trip “%(name)s” is on your calendar. Now fill the suitcase.", name=trip.name), "success")
        return _back(trip)

    today = date.today()
    trips = db.session.scalars(
        db.select(Trip).filter_by(user_id=current_user.id).order_by(Trip.start_date.desc())
    ).all()
    upcoming = sorted((t for t in trips if t.end_date >= today), key=lambda t: t.start_date)
    past = [t for t in trips if t.end_date < today]
    return render_template("trips/index.html", title=_("Trips"), form=form,
                           upcoming=upcoming, past=past)


# ---------- The pack page ----------

@bp.route("/<int:trip_id>")
def pack(trip_id):
    trip = get_own_trip_or_404(trip_id)
    in_suitcase = {link.item_id for link in trip.item_links}
    outfits = db.session.scalars(
        db.select(Outfit).filter_by(user_id=current_user.id).order_by(db.func.lower(Outfit.name))
    ).all()
    return render_template("trips/pack.html", title=trip.name, trip=trip,
                           groups=my_items_by_category(), in_suitcase=in_suitcase,
                           outfits=[o for o in outfits if o.items])


@bp.route("/<int:trip_id>/edit", methods=["GET", "POST"])
def edit(trip_id):
    trip = get_own_trip_or_404(trip_id)
    form = TripForm(obj=trip)
    form.submit.label.text = _("Save")
    if form.validate_on_submit():
        form.populate_obj(trip)  # copies every field with the same name onto trip
        trip.name = trip.name.strip()
        db.session.commit()
        flash(_("Trip saved."), "success")
        return _back(trip)
    return render_template("trips/edit.html", title=_("Edit %(name)s", name=trip.name), form=form, trip=trip)


@bp.route("/<int:trip_id>/delete", methods=["POST"])
def delete(trip_id):
    # CSRFProtect (app/extensions.py) has already checked the form's token.
    trip = get_own_trip_or_404(trip_id)
    db.session.delete(trip)  # the suitcase rows go too (cascade); clothes stay
    db.session.commit()
    flash(_("Deleted the trip “%(name)s”. Your clothes are still in your wardrobe.", name=trip.name), "info")
    return redirect(url_for("trips.index"))


# ---------- Filling the suitcase ----------

def _add(trip, items):
    """Put items in the suitcase; ones already in it are skipped."""
    have = {link.item_id for link in trip.item_links}
    added = [item for item in items if item.id not in have]
    for item in added:
        trip.item_links.append(TripItem(item=item))
    db.session.commit()
    return added


@bp.route("/<int:trip_id>/items/<int:item_id>", methods=["POST"])
def add_item(trip_id, item_id):
    trip = get_own_trip_or_404(trip_id)
    item = db.session.scalar(Item.owned_by(current_user.id).filter_by(id=item_id))
    if item is None:
        abort(404)
    added = _add(trip, [item])
    if wants_json():
        links = [link for link in trip.item_links if link.item_id in {i.id for i in added}]
        return jsonify(added=[item.id for item in added], **_counts(trip),
                       html="".join(render_template("trips/_suitcase_item.html", trip=trip, link=link)
                                    for link in links))
    return _back(trip)


@bp.route("/<int:trip_id>/outfits/<int:outfit_id>", methods=["POST"])
def add_outfit(trip_id, outfit_id):
    """Drop a whole outfit in: all its items at once."""
    trip = get_own_trip_or_404(trip_id)
    outfit = db.session.scalar(db.select(Outfit).filter_by(id=outfit_id, user_id=current_user.id))
    if outfit is None:
        abort(404)
    added = _add(trip, [item for item in outfit.items if not item.is_wish])
    if wants_json():
        ids = {item.id for item in added}
        return jsonify(added=sorted(ids), **_counts(trip),
                       html="".join(render_template("trips/_suitcase_item.html", trip=trip, link=link)
                                    for link in trip.item_links if link.item_id in ids))
    flash(ngettext("Added %(num)d item from “%(name)s”.", "Added %(num)d items from “%(name)s”.",
                   len(added), name=outfit.name), "success")
    return _back(trip)


def _get_link_or_404(trip, item_id):
    link = next((link for link in trip.item_links if link.item_id == item_id), None)
    if link is None:
        abort(404)
    return link


@bp.route("/<int:trip_id>/items/<int:item_id>/remove", methods=["POST"])
def remove_item(trip_id, item_id):
    trip = get_own_trip_or_404(trip_id)
    trip.item_links.remove(_get_link_or_404(trip, item_id))  # delete-orphan deletes the row
    db.session.commit()
    return jsonify(removed=item_id, **_counts(trip)) if wants_json() else _back(trip)


@bp.route("/<int:trip_id>/items/<int:item_id>/packed", methods=["POST"])
def toggle_packed(trip_id, item_id):
    trip = get_own_trip_or_404(trip_id)
    link = _get_link_or_404(trip, item_id)
    link.packed = not link.packed
    db.session.commit()
    return jsonify(item=item_id, is_packed=link.packed, **_counts(trip)) if wants_json() else _back(trip)


@bp.app_template_filter("trip_dates")
def trip_dates(trip):
    """"14.10.2026 – 16.10.2026 · 3 days" for a trip."""
    days = ngettext("%(num)d day", "%(num)d days", trip.days)
    return f"{format_date(trip.start_date)} – {format_date(trip.end_date)} · {days}"
