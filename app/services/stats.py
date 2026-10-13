"""Numbers about your wardrobe, for the stats page and the home page.

Every function takes a user id and asks the database to do the counting
(GROUP BY, MAX, COUNT) instead of loading every row into Python.
"""
from datetime import date, timedelta

from app.extensions import db
from app.models import OWNED, Category, Item, WearLog, WearLogItem
from app.wardrobe.choices import COLORS

# "Not worn lately" means: last worn more than this many days ago.
STALE_AFTER_DAYS = 30


def last_worn_dates(user_id):
    """{item_id: date it was last worn} for items worn at least once.

    Every wear is in the wear log (planned outfits marked worn and looks
    logged from loose items). In SQL:

        SELECT wear_log_item.item_id, MAX(wear_log.date)
        FROM wear_log JOIN wear_log_item ON same log
        WHERE user_id = ?
        GROUP BY wear_log_item.item_id
    """
    rows = db.session.execute(
        db.select(WearLogItem.item_id, db.func.max(WearLog.date))
        .join(WearLog, WearLog.id == WearLogItem.wear_log_id)
        .where(WearLog.user_id == user_id)
        .group_by(WearLogItem.item_id)
    )
    return dict(rows.all())


def last_worn_date(item):
    """The last day this one item was worn, or None."""
    return db.session.scalar(
        db.select(db.func.max(WearLog.date))
        .join(WearLogItem, WearLogItem.wear_log_id == WearLog.id)
        .where(WearLogItem.item_id == item.id)
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
    # Only clothes you own: wishlist items don't count.
    mine = Item.owned_by(user_id)

    item_count = db.session.scalar(db.select(db.func.count()).select_from(mine.subquery()))
    total_wears = db.session.scalar(
        db.select(db.func.coalesce(db.func.sum(Item.times_worn), 0))
        .where(Item.user_id == user_id, Item.status == OWNED)
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
        db.select(Item.color, db.func.count(Item.id))
        .where(Item.user_id == user_id, Item.status == OWNED).group_by(Item.color)
    ).all()
    by_category = db.session.execute(
        db.select(Category.name, db.func.count(Item.id))
        .join(Item.category).where(Item.user_id == user_id, Item.status == OWNED).group_by(Category.name)
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
