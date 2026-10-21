"""Calendar logic shared by the planner page and the JSON API.

Like outfit_rules.py, nothing here knows about requests or templates.
"""
import calendar
from datetime import date, timedelta

from flask_babel import gettext as _
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.i18n import weekday_short
from app.models import ScheduledOutfit

# Weeks start on Monday (calendar's day 0).
CAL = calendar.Calendar(firstweekday=calendar.MONDAY)


def weekday_names():
    """["Mon", "Tue", ...] / ["пн", "вт", ...]: the calendar's header row.

    A function, not a list, because the language is only known during a
    request. 5 Jan 2026 was a Monday; the next 6 days give the rest.
    """
    monday = date(2026, 1, 5)
    return [weekday_short(monday + timedelta(days=n)) for n in range(7)]


class ScheduleError(Exception):
    """Something the user should be told, e.g. "already planned that day"."""


def parse_month(text, today=None):
    """"2026-10" -> date(2026, 10, 1). Anything else -> the current month."""
    today = today or date.today()
    try:
        year, month = (int(part) for part in text.split("-"))
        return date(year, month, 1)
    except (AttributeError, ValueError):
        return today.replace(day=1)


def shift_month(first_day, months):
    """date(2026, 12, 1) shifted by +1 -> date(2027, 1, 1)."""
    index = first_day.year * 12 + (first_day.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


def month_weeks(first_day):
    """The month as a list of weeks; each week is 7 dates, Monday first.

    The first and last week include a few days of the neighbouring
    months, so every row is full. The template greys those out.
    """
    return CAL.monthdatescalendar(first_day.year, first_day.month)


def entries_between(user_id, start, end):
    """{date: [ScheduledOutfit, ...]} for start <= date <= end."""
    rows = db.session.scalars(
        db.select(ScheduledOutfit)
        .filter_by(user_id=user_id)
        .where(ScheduledOutfit.date.between(start, end))
        .order_by(ScheduledOutfit.date, ScheduledOutfit.created_at)
    )
    by_day = {}
    for entry in rows:
        by_day.setdefault(entry.date, []).append(entry)
    return by_day


def coming_week(user_id, today=None):
    """Today plus the next 6 days, for the home page: [(date, [entries]), ...]."""
    today = today or date.today()
    days = [today + timedelta(days=n) for n in range(7)]
    by_day = entries_between(user_id, days[0], days[-1])
    return [(day, by_day.get(day, [])) for day in days]


def schedule_outfit(outfit, day, note=None):
    """Put an outfit on a day. Raises ScheduleError if it's already there."""
    entry = ScheduledOutfit(user_id=outfit.user_id, outfit=outfit, date=day, note=note or None)
    db.session.add(entry)
    try:
        db.session.commit()
    except IntegrityError:
        # The UniqueConstraint (outfit_id, date) said no.
        db.session.rollback()
        raise ScheduleError(_("“%(name)s” is already planned for that day.", name=outfit.name))
    return entry
