"""Numbers about your wardrobe, for the stats page and the home page.

Every function takes a user id and asks the database to do the counting
(GROUP BY, MAX, COUNT) instead of loading every row into Python.
"""
from datetime import date, timedelta

from app.extensions import db
from app.models import Category, Item, OutfitItem, ScheduledOutfit
from app.wardrobe.choices import COLORS

# "Not worn lately" means: last worn more than this many days ago.
STALE_AFTER_DAYS = 30


def last_worn_dates(user_id):
    """{item_id: date it was last worn} for items worn at least once.

    An item is "worn" on a day when an outfit containing it is marked worn
    in the planner. In SQL:

        SELECT outfit_item.item_id, MAX(scheduled_outfit.date)
        FROM scheduled_outfit JOIN outfit_item ON same outfit
        WHERE worn AND user_id = ?
        GROUP BY outfit_item.item_id
    """
    rows = db.session.execute(
        db.select(OutfitItem.item_id, db.func.max(ScheduledOutfit.date))
        .join(ScheduledOutfit, ScheduledOutfit.outfit_id == OutfitItem.outfit_id)
        .where(ScheduledOutfit.user_id == user_id, ScheduledOutfit.worn)
        .group_by(OutfitItem.item_id)
    )
    return dict(rows.all())


def last_worn_date(item):
    """The last day this one item was worn, or None."""
    return db.session.scalar(
        db.select(db.func.max(ScheduledOutfit.date))
        .join(OutfitItem, OutfitItem.outfit_id == ScheduledOutfit.outfit_id)
        .where(OutfitItem.item_id == item.id, ScheduledOutfit.worn)
    )


def not_worn_lately(user_id, today=None, limit=None):
    """Items you have worn before, but not in the last STALE_AFTER_DAYS days.

    Oldest last-wear first: those are the ones you've forgotten longest.
    Returns [(item, last_worn_date), ...].
    """
    today = today or date.today()
    cutoff = today - timedelta(days=STALE_AFTER_DAYS)
    last_worn = last_worn_dates(user_id)
    stale_ids = [item_id for item_id, day in last_worn.items() if day < cutoff]
    if not stale_ids:
        return []
    items = db.session.scalars(db.select(Item).where(Item.id.in_(stale_ids))).all()
    pairs = sorted(((item, last_worn[item.id]) for item in items), key=lambda pair: pair[1])
    return pairs[:limit] if limit else pairs


def breakdown(rows):
    """[(label, count), ...] -> [{"label", "count", "percent"}, ...], biggest first.

    percent is relative to the biggest group, so the longest bar fills
    the whole width and the others are drawn in proportion.
    """
    rows = sorted(rows, key=lambda row: (-row[1], row[0]))
    biggest = rows[0][1] if rows else 0
    return [
        {"label": label, "count": count, "percent": round(count * 100 / biggest)}
        for label, count in rows
    ]


def wardrobe_stats(user_id, today=None):
    """Everything the stats page shows, in one dict."""
    mine = db.select(Item).filter_by(user_id=user_id)

    item_count = db.session.scalar(db.select(db.func.count()).select_from(mine.subquery()))
    total_wears = db.session.scalar(
        db.select(db.func.coalesce(db.func.sum(Item.times_worn), 0)).where(Item.user_id == user_id)
    )
    most_worn = db.session.scalars(
        mine.where(Item.times_worn > 0).order_by(Item.times_worn.desc(), Item.name).limit(5)
    ).all()
    # The bottom 5, leaving out anything already in the top 5.
    least_worn = db.session.scalars(
        mine.where(Item.times_worn > 0, Item.id.not_in([i.id for i in most_worn]))
        .order_by(Item.times_worn, Item.name).limit(5)
    ).all()
    never_worn = db.session.scalars(
        mine.where(Item.times_worn == 0).order_by(Item.created_at)
    ).all()

    # GROUP BY: one row per color with how many items have it.
    by_color = db.session.execute(
        db.select(Item.color, db.func.count(Item.id)).where(Item.user_id == user_id).group_by(Item.color)
    ).all()
    by_category = db.session.execute(
        db.select(Category.name, db.func.count(Item.id))
        .join(Item.category).where(Item.user_id == user_id).group_by(Category.name)
    ).all()

    colors = breakdown(by_color)
    for row in colors:
        row["swatch"] = COLORS.get(row["label"], "")

    return {
        "item_count": item_count,
        "total_wears": total_wears,
        "never_worn_count": len(never_worn),
        "most_worn": most_worn,
        "least_worn": least_worn,
        "never_worn": never_worn,
        "not_worn_lately": not_worn_lately(user_id, today),
        "by_color": colors,
        "by_category": breakdown(by_category),
        "stale_days": STALE_AFTER_DAYS,
    }
