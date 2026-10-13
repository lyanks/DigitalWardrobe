from datetime import date, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.dates import format_date
from app.extensions import db
from app.models import Item, Outfit, ScheduledOutfit, WearLog
from app.outfits.routes import get_own_outfit_or_404, my_items_by_category
from app.planner.forms import LogLookForm, ScheduleForm
from app.services.combo_check import WINDOW_DAYS, check_combo
from app.services.outfit_rules import outfit_problems, sort_by_slot
from app.services.planner import (
    WEEKDAY_NAMES, ScheduleError, entries_between, month_weeks, parse_month,
    schedule_outfit, shift_month,
)

bp = Blueprint("planner", __name__, url_prefix="/planner")


@bp.before_request
@login_required
def require_login():
    """The calendar is private."""


def get_own_entry_or_404(entry_id):
    entry = db.session.scalar(
        db.select(ScheduledOutfit).filter_by(id=entry_id, user_id=current_user.id)
    )
    if entry is None:
        abort(404)
    return entry


def _my_outfits():
    return db.session.scalars(
        db.select(Outfit).filter_by(user_id=current_user.id).order_by(db.func.lower(Outfit.name))
    ).all()


def _back_to_month(day):
    """Redirect to the planner page showing the month of `day`."""
    return redirect(url_for("planner.index", month=day.strftime("%Y-%m")))


# ---------- The month page ----------

@bp.route("")
def index():
    # /planner?month=2026-10. Without it (or with nonsense) you get this month.
    first_day = parse_month(request.args.get("month"))
    weeks = month_weeks(first_day)
    # One query for the whole visible grid, including the grey days of
    # the neighbouring months at the start and the end.
    entries = entries_between(current_user.id, weeks[0][0], weeks[-1][-1])

    outfits = _my_outfits()
    form = ScheduleForm()
    form.outfit_id.choices = [(o.id, o.name) for o in outfits]
    if form.date.data is None:
        today = date.today()
        # Pre-fill the date: today if you're looking at this month, else the 1st.
        form.date.data = today if today.replace(day=1) == first_day else first_day

    return render_template(
        "planner/index.html", title="Planner", first_day=first_day, weeks=weeks,
        entries=entries, weekday_names=WEEKDAY_NAMES, today=date.today(),
        prev_month=shift_month(first_day, -1), next_month=shift_month(first_day, 1),
        outfits=outfits, form=form,
    )


# ---------- Schedule (the plain form; calendar.js uses the API instead) ----------

@bp.route("/schedule", methods=["POST"])
def schedule():
    form = ScheduleForm()
    form.outfit_id.choices = [(o.id, o.name) for o in _my_outfits()]
    if not form.validate_on_submit():
        for errors in form.errors.values():
            for error in errors:
                flash(error, "error")
        return redirect(url_for("planner.index"))

    outfit = get_own_outfit_or_404(form.outfit_id.data)
    try:
        schedule_outfit(outfit, form.date.data, (form.note.data or "").strip())
    except ScheduleError as error:
        flash(str(error), "error")
    else:
        flash(f"Planned “{outfit.name}” for {form.date.data.strftime('%A')} {format_date(form.date.data)}.", "success")
        notice = check_combo(current_user.id, outfit.items, form.date.data)
        if notice:
            flash(notice, "info")
    return _back_to_month(form.date.data)


# ---------- Worn / not worn ----------

@bp.route("/<int:entry_id>/worn", methods=["POST"])
def toggle_worn(entry_id):
    entry = get_own_entry_or_404(entry_id)
    if not entry.worn and not entry.can_be_worn:
        flash("You can't have worn it yet: that day is in the future.", "error")
    else:
        entry.set_worn(not entry.worn)
        db.session.commit()
        if entry.worn:
            flash(f"Marked “{entry.outfit.name}” as worn. Each of its items counts one more wear.", "success")
        else:
            flash(f"“{entry.outfit.name}” is no longer marked as worn.", "info")
    return _back_to_month(entry.date)


# ---------- Unschedule ----------

@bp.route("/<int:entry_id>/delete", methods=["POST"])
def delete(entry_id):
    entry = get_own_entry_or_404(entry_id)
    day = entry.date
    # If it was marked worn, take those wears back off the items first.
    entry.set_worn(False)
    db.session.delete(entry)
    db.session.commit()
    flash(f"Removed “{entry.outfit.name}” from {day.strftime('%A')} {format_date(day)}.", "info")
    return _back_to_month(day)


# ---------- Log a look (idea #1) ----------

@bp.route("/log", methods=["GET", "POST"])
def log_look():
    """Say what you wore on a day by ticking loose items, no outfit needed."""
    groups = my_items_by_category()
    form = LogLookForm()
    form.item_ids.choices = [(item.id, item.name) for _, items in groups for item in items]
    if form.date.data is None and not form.is_submitted():
        form.date.data = date.today()

    if form.validate_on_submit():
        day = form.date.data
        items = db.session.scalars(
            Item.owned_by(current_user.id).where(Item.id.in_(form.item_ids.data))
        ).all()
        problems = outfit_problems(items)
        if day > date.today():
            form.date.errors.append("That day hasn't happened yet. Plan it in the calendar instead.")
        elif problems:
            form.item_ids.errors.extend(problems)
        else:
            # Check before saving, or the look would match itself.
            notice = check_combo(current_user.id, items, day)
            WearLog.record(current_user.id, day, sort_by_slot(items))
            db.session.commit()
            flash(f"Logged your look for {day.strftime('%A')} {format_date(day)}.", "success")
            if notice:
                flash(notice, "info")
            return redirect(url_for("planner.log_look"))

    # The last week of logs, newest first, so a mistake is easy to spot.
    since = date.today() - timedelta(days=WINDOW_DAYS)
    recent = db.session.scalars(
        db.select(WearLog).filter_by(user_id=current_user.id).where(WearLog.date >= since)
        .order_by(WearLog.date.desc(), WearLog.created_at.desc())
    ).all()
    return render_template("planner/log.html", title="Log a look", form=form,
                           groups=groups, recent=recent)


@bp.route("/log/<int:log_id>/delete", methods=["POST"])
def delete_log(log_id):
    """Remove a look logged by mistake (and its wears from the items)."""
    log = db.session.scalar(db.select(WearLog).filter_by(id=log_id, user_id=current_user.id))
    if log is None:
        abort(404)
    if log.outfit_id is not None:
        # It came from the planner: untick it there, so both stay in step.
        flash("That look came from the planner. Untick “Worn” there instead.", "error")
    else:
        log.undo()
        db.session.commit()
        flash(f"Removed the look from {format_date(log.date)}.", "info")
    return redirect(url_for("planner.log_look"))
