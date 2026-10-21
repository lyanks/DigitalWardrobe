"""Idea #1: "You wore this combo recently".

Before you wear (or plan) a look, check the wear log: did the same top and
bottom (or the same dress) go out together in the last week? If so, the
page shows a gentle note. It never blocks anything.

The logic is three small steps, and only the middle one touches the
database:
1. combo_ids(items): which items make the look recognisable.
2. worn_between(...): {day: set of item ids worn that day}.
3. matching_days(combo, worn): the days whose set contains the combo.
"""
from datetime import timedelta

from babel.dates import format_date as babel_format_date
from flask import has_app_context
from flask_babel import gettext as _

from app.dates import format_date
from app.extensions import db
from app.i18n import weekday
from app.models import WearLog, WearLogItem

# How far back to look.
WINDOW_DAYS = 7

# The slots that make a look recognisable. Shoes and accessories don't:
# wearing your only pair of trainers every day is fine.
KEY_SLOTS = {"top", "bottom", "full"}


def combo_ids(items):
    """The ids worth checking, or an empty set if there's no combo.

    A combo is a top with a bottom, or a dress / full-body item (with a top
    over it, if there is one). A top on its own isn't a combo.
    """
    key = [item for item in items if item.category.slot in KEY_SLOTS]
    slots = {item.category.slot for item in key}
    if "full" in slots or {"top", "bottom"} <= slots:
        return {item.id for item in key}
    return set()


def worn_between(user_id, start, end):
    """{date: {item ids worn that day}} for start <= date <= end.

    Two looks on one day (day + evening) count as one day: the sets are
    joined with |=.
    """
    rows = db.session.execute(
        db.select(WearLog.date, WearLogItem.item_id)
        .join(WearLogItem, WearLogItem.wear_log_id == WearLog.id)
        .where(WearLog.user_id == user_id, WearLog.date.between(start, end))
    )
    worn = {}
    for day, item_id in rows:
        worn.setdefault(day, set()).add(item_id)
    return worn


def matching_days(combo, worn):
    """The days (oldest first) whose items include the whole combo.

    `combo <= ids` is Python's "is a subset of" for sets: True when every
    id in combo is also in ids. Extra items that day (other shoes, a
    jacket) don't matter.
    """
    if not combo:
        return []
    return sorted(day for day, ids in worn.items() if combo <= ids)


def recent_combo_days(user_id, items, day, days=WINDOW_DAYS):
    """Days in the `days` days before `day` when this combo was worn."""
    combo = combo_ids(items)
    if not combo:
        return []
    worn = worn_between(user_id, day - timedelta(days=days), day - timedelta(days=1))
    return matching_days(combo, worn)


def _day_name(day):
    """"Wednesday" in the page's language.

    app.i18n.weekday needs the running app to know the language; the tests
    call combo_notice without one, so then it's English.
    """
    return weekday(day) if has_app_context() else babel_format_date(day, "EEEE", locale="en")


def combo_notice(items, dates):
    """The sentence for the page, e.g.
    "You wore Blue shirt with Jeans on Wednesday 07.10.2026."
    None when there's nothing to say.
    """
    if not dates:
        return None
    combo = combo_ids(items)
    names = [item.name for item in items if item.id in combo]
    if len(names) == 1:
        what = names[0]
    else:
        what = _("%(items)s with %(last)s", items=", ".join(names[:-1]), last=names[-1])
    days = [f"{_day_name(d)} {format_date(d)}" for d in dates[-2:]]
    when = days[0] if len(days) == 1 else _("%(first)s and %(second)s", first=days[0], second=days[1])
    return _("You wore %(what)s on %(when)s.", what=what, when=when)


def check_combo(user_id, items, day, days=WINDOW_DAYS):
    """recent_combo_days + combo_notice in one call: the notice or None."""
    return combo_notice(items, recent_combo_days(user_id, items, day, days))
